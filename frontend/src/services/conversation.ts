import type { z } from 'zod';
import { React } from '../platform/react-host';
import { preview, timelineSchema } from './preview';

type Timeline = z.infer<typeof timelineSchema>;
type Message = Timeline['messages'][number];
const maximumMessages = 5000;

function appendMessages(previous: Message[], incoming: Message[]) {
  const last = previous[previous.length - 1];
  const first = incoming[0];
  if (last?.kind === 'tools' && first?.kind === 'tools') {
    return [...previous.slice(0, -1), { ...last, tools: [...last.tools, ...first.tools] }, ...incoming.slice(1)];
  }
  return [...previous, ...incoming];
}

export function useConversation(path: string) {
  const empty = { path, data: null as Timeline | null, messages: [] as Message[], loaded: 0, loading: true, error: null as string | null, hasMore: false, capped: false };
  const [state, setState] = React.useState(empty);
  const load = React.useRef<(() => Promise<void>) | null>(null);
  React.useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let pending = false;
    let offset = 0;
    let more = true;
    setState({ path, data: null, messages: [], loaded: 0, loading: true, error: null, hasMore: false, capped: false });
    const next = async () => {
      if (!active || pending || !more) return;
      pending = true;
      setState((current) => ({ ...current, loading: true, error: null }));
      try {
        const limit = Math.min(100, maximumMessages - offset);
        const result = await preview(`${path}&latest=true&offset=${offset}&limit=${limit}`, timelineSchema, { signal: controller.signal });
        const page = result.data.pagination;
        if (page.offset !== offset || !Number.isInteger(page.returned) || page.returned < 0 || page.returned > limit || result.data.messages.length > page.returned || (page.has_more && page.returned === 0)) throw new Error('会话加载进度异常，请关闭详情后重试');
        if (!active) return;
        offset += page.returned;
        more = page.has_more && offset < maximumMessages;
        setState((current) => ({ path, data: result.data, messages: appendMessages(result.data.messages, current.messages), loaded: offset, loading: false, error: null, hasMore: more, capped: page.has_more && !more }));
      } catch (reason) {
        if (active) setState((current) => ({ ...current, loading: false, error: reason instanceof Error ? reason.message : '会话加载失败' }));
      } finally {
        pending = false;
      }
    };
    load.current = next;
    void next();
    return () => { active = false; controller.abort(); load.current = null; };
  }, [path]);
  return { ...(state.path === path ? state : empty), retry: () => { void load.current?.(); } };
}
