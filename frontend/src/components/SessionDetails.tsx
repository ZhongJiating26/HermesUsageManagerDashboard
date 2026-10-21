import type { z } from 'zod';
import { React } from '../platform/react-host';
import { query, timelineSchema, type Filters, type Selection, type Session } from '../services/preview';
import { useConversation } from '../services/conversation';
import { tokens, Empty, ResourceState, time } from './common';
import { InfoTip } from './InfoTip';

type Message = z.infer<typeof timelineSchema>['messages'][number];

function MessageBubble({ message }: { message: Message }) {
  const [expanded, setExpanded] = React.useState(false);
  const long = message.text.length > 320 || message.text.split('\n').length > 6;
  return <article className={`hum-message hum-message-${message.kind}`}>
    <div className="hum-message-meta">{message.kind === 'assistant' ? 'Hermes' : '用户'}{message.time && <time dateTime={message.time}>{time(message.time)}</time>}</div>
    <div className={`hum-message-bubble${long && !expanded ? ' hum-message-collapsed' : ''}`}><p>{message.text || '—'}</p></div>
    {long && <button className="hum-message-expand" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? '收起内容' : '展开完整内容'}<span className="hum-chevron" aria-hidden="true" /></button>}
  </article>;
}

function ToolGroup({ message }: { message: Message }) {
  const success = message.tools.filter((tool) => tool.success === true).length;
  const failed = message.tools.filter((tool) => tool.success === false).length;
  const unknown = message.tools.some((tool) => tool.success === null);
  return <details className="hum-tool-group">
    <summary><span>工具调用 <span className="hum-tool-count">{message.tools.length} 次</span></span><small>成功 {success} / 失败 {failed}{unknown && ' · 含未知状态'}</small><span className="hum-chevron" aria-hidden="true" /></summary>
    <div className="hum-tool-list">{message.tools.map((tool) => <details className="hum-tool-item" key={tool.id}>
      <summary><span className="hum-tool-name">{tool.name}</span>{tool.time && <time dateTime={tool.time}>{time(tool.time)}</time>}<span className="hum-tool-status" aria-label={tool.success === null ? '状态未知' : tool.success ? '成功' : '失败'}>{tool.success === null ? '未知' : tool.success ? '成功' : '失败'}</span><span className="hum-chevron" aria-hidden="true" /></summary>
      <dl className="hum-tool-body"><dt>接口</dt><dd>{tool.name}</dd><dt>请求参数</dt><dd><pre>{tool.args}</pre></dd><dt>执行结果</dt><dd><pre>{tool.result}</pre></dd></dl>
    </details>)}</div>
  </details>;
}

export function SessionDetails({ session, filters, selection }: { session: Session; filters: Filters; selection: Selection }) {
  const resource = useConversation(`/sessions/${encodeURIComponent(session.id)}/timeline?${query(selection)}`);
  const scroll = React.useRef<HTMLDivElement>(null);
  const sentinel = React.useRef<HTMLDivElement>(null);
  const data = resource.data;
  React.useEffect(() => {
    if (!resource.hasMore || resource.loading || resource.error || !scroll.current || !sentinel.current) return;
    const observer = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) resource.retry(); }, { root: scroll.current, rootMargin: '0px 0px 100px 0px' });
    observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, [resource.hasMore, resource.loading, resource.error, resource.loaded, resource.retry]);
  return <div className="hum-session-detail">
    <header className="hum-session-summary">
      <div className="hum-title"><h2>{data?.session.title || '对话详情'}</h2><InfoTip label="对话详情说明">消息连续滚动，接近底部时按需读取；消息数为已加载的原始消息数量，不代表完整会话总数。单次查看最多读取5000条，达到上限会明确提示。MCP 调用为当前筛选范围统计，不等于全部工具调用。缺少标题、消息时间或用量时不补造；工具参数及结果仍遵循现有读取权限。</InfoTip></div>
      <dl className="hum-session-metadata">
        <div className="hum-session-id"><dt>会话 ID</dt><dd>{data?.session.source_id || session.id}</dd></div>
        <div className="hum-session-start"><dt>会话开始时间</dt><dd>{time(data?.session.time || session.time)}</dd></div>
        <div><dt>部门</dt><dd>{filters.departments.find((item) => item.id === session.department_id)?.name ?? '未归属'}</dd></div>
        <div><dt>用户</dt><dd>{filters.users.find((item) => item.id === session.user_id)?.name ?? '未归属'}</dd></div>
        <div><dt>已加载消息</dt><dd>{data ? `${resource.loaded} 条` : '—'}</dd></div>
        <div><dt>MCP 调用</dt><dd>{session.mcp_calls} 次</dd></div>
        <div><dt>输入未命中</dt><dd>{tokens(session.input)}</dd></div>
        <div><dt>输出</dt><dd>{tokens(session.output)}</dd></div>
        <div><dt>缓存读取</dt><dd>{tokens(session.cached)}</dd></div>
      </dl>
    </header>
    <div ref={scroll} className="hum-conversation" role="region" aria-label="对话记录" tabIndex={0} aria-busy={resource.loading}>
      {data && (resource.messages.length === 0 && !resource.hasMore && !resource.loading ? <Empty text="没有可展示的消息" /> : resource.messages.map((message) => message.kind === 'tools' ? <ToolGroup key={message.id} message={message} /> : <MessageBubble key={message.id} message={message} />))}
      {resource.loading && data ? <div className="hum-conversation-status" role="status">正在加载更多消息…</div> : <ResourceState {...resource} />}
      {resource.capped && <div className="hum-conversation-status" role="status">本次已加载5000条消息，已达到安全查看上限，后续内容尚未加载。</div>}
      <div ref={sentinel} className="hum-conversation-sentinel" aria-hidden="true" />
    </div>
  </div>;
}
