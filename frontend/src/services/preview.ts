import { z } from 'zod';
import { getSDK } from '../platform/hermes-sdk';
import { React } from '../platform/react-host';

export const departmentSchema = z.object({ id: z.string(), name: z.string() });
export const userSchema = z.object({ id: z.string(), name: z.string(), external_id: z.string(), department_id: z.string(), profile: z.string(), platform: z.string().default('feishu') });
export const filtersSchema = z.object({ departments: departmentSchema.array(), users: userSchema.array(), servers: departmentSchema.array(), anchor: z.string(), role: z.string() });
const tokenFields = { input: z.number().nonnegative().nullable(), cached: z.number().nonnegative().nullable(), output: z.number().nonnegative().nullable() };
export const requestSchema = z.object({ id: z.string(), time: z.string(), department_id: z.string(), user_id: z.string(), model: z.string(), provider: z.string(),
  session_id: z.string(), profile: z.string(), status: z.enum(['success', 'failed']), ...tokenFields, duration_ms: z.number().nullable(), cost: z.number().nullable() });
export const sessionSchema = z.object({ id: z.string(), time: z.string(), department_id: z.string(), user_id: z.string(), profile: z.string(), platform: z.string(), ...tokenFields, mcp_calls: z.number() });
const quantity = z.number().nullable();
const distributionSchema = z.object({ id: z.string(), name: z.string(), tokens: quantity, cost: quantity, input: quantity, cached: quantity, output: quantity });
export const analyticsSchema = z.object({ count: z.number(), kpis: z.object({ input: quantity, cached: quantity, output: quantity, total_tokens: quantity, input_cost: quantity, cached_cost: quantity, output_cost: quantity, cost: quantity, active: z.number(), unknown_cost: z.number(), unknown_cache: z.number(), primary_model: z.string().nullable() }),
  trend: z.object({ day: z.string(), input: quantity, cached: quantity, output: quantity, total_tokens: quantity, active: z.number(), calls: z.number() }).array(),
  distributions: z.object({ department: distributionSchema.array(), model: distributionSchema.array(), provider: distributionSchema.array(), user: distributionSchema.array() }),
  tools: z.object({ id: z.string(), name: z.string(), server_id: z.string(), calls: z.number(), failed: z.number(), duration_ms: quantity }).array() });
export const priceSchema = z.object({ id: z.string(), model: z.string(), provider: z.string(), input: z.number(), cached: z.number(), output: z.number(), valid_from: z.string(), valid_to: z.string().nullable(), enabled: z.boolean() });
export const unpricedSchema = z.object({ id: z.string(), model: z.string(), provider: z.string(), valid_from: z.string(), valid_to: z.string(), request_count: z.number(), reason: z.string() });
export const timelineSchema = z.object({ session: z.object({ id: z.string(), source_id: z.string().optional(), title: z.string().nullable().optional(), profile: z.string(), platform: z.string(), time: z.string() }), messages: z.object({ id: z.string(), kind: z.enum(['user', 'assistant', 'tools']), text: z.string(), time: z.string().datetime({ offset: true }).nullable().optional(), tools: z.object({ id: z.string(), name: z.string(), success: z.boolean().nullable(), args: z.string(), result: z.string(), time: z.string().datetime({ offset: true }).nullable().optional() }).array() }).array(), pagination: z.object({ offset: z.number(), limit: z.number(), has_more: z.boolean(), returned: z.number() }) });
export type Filters = z.infer<typeof filtersSchema>;
export type User = z.infer<typeof userSchema>;
export type Department = z.infer<typeof departmentSchema>;
export type Analytics = z.infer<typeof analyticsSchema>;
export type ModelRequest = z.infer<typeof requestSchema>;
export type Session = z.infer<typeof sessionSchema>;
export type Price = z.infer<typeof priceSchema>;
export type Distribution = z.infer<typeof distributionSchema>;
export type Selection = { start: string; end: string; department_id: string; user_id: string; server_id: string; all_time?: boolean };
export const metaSchema = z.object({ data_source: z.enum(['mock', 'live']), tz: z.string(), total: z.number().optional(), page: z.number().optional(), page_size: z.number().optional() });
let expectedSource: 'mock' | 'live' = 'live';
export function configureSource(source: 'mock' | 'live') { expectedSource = source; }

export async function preview<T>(path: string, schema: z.ZodType<T>, init?: RequestInit) {
  const value = await getSDK().fetchJSON(`/api/plugins/hermes-usage-manager${path}`, init);
  const parsed = z.object({ data: schema, meta: metaSchema }).safeParse(value);
  if (!parsed.success || parsed.data.meta.data_source !== expectedSource) throw new Error('接口响应格式或数据源不兼容');
  return parsed.data;
}

export function query(selection: Selection, extra: Record<string, string | number> = {}) {
  const { start, end, all_time, ...filters } = selection;
  return new URLSearchParams({ from: start, to: end, tz: 'Asia/Shanghai', ...filters, ...(all_time ? { all_time: 'true' } : {}), ...Object.fromEntries(Object.entries(extra).map(([key, value]) => [key, String(value)])) }).toString();
}

export function useResource<T>(path: string, schema: z.ZodType<T>, revision = 0) {
  const [state, setState] = React.useState<{ data: T | null; total: number; loading: boolean; error: string | null; path: string; revision: number }>({ data: null, total: 0, loading: true, error: null, path, revision });
  const [attempt, setAttempt] = React.useState(0);
  React.useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setState({ data: null, total: 0, loading: true, error: null, path, revision });
    const load = async () => {
      const result = await preview(path, schema, { signal: controller.signal });
      if (/^\/(people\/(users|departments)|models\/(prices|unpriced))$/.test(path) && Array.isArray(result.data)) {
        const accumulated: unknown[] = [...result.data];
        for (let page = 2; accumulated.length < (result.meta.total ?? 0); page += 1) {
          if (page > 100) throw new Error('管理列表超过加载上限');
          const next = await preview(`${path}?page=${page}&page_size=100`, schema, { signal: controller.signal });
          if (!Array.isArray(next.data) || !next.data.length) throw new Error('管理列表分页不一致，请刷新重试');
          accumulated.push(...next.data);
        }
        result.data = schema.parse(accumulated);
      }
      return result;
    };
    load().then((result) => {
      if (active) setState({ data: result.data, total: result.meta.total ?? 0, loading: false, error: null, path, revision });
    }).catch((reason: unknown) => {
      if (active) setState({ data: null, total: 0, loading: false, error: reason instanceof Error ? reason.message : '请求失败', path, revision });
    });
    return () => { active = false; controller.abort(); };
  }, [path, schema, attempt, revision]);
  const current = state.path === path && state.revision === revision;
  return { ...state, data: current ? state.data : null, loading: !current || state.loading, retry: () => setAttempt((value) => value + 1) };
}

export async function mutate(path: string, method: string, body?: unknown) {
  const result = await getSDK().fetchJSON(`/api/plugins/hermes-usage-manager${path}`, { method, headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  const parsed = z.object({ data: z.unknown(), meta: metaSchema }).safeParse(result);
  if (!parsed.success || parsed.data.meta.data_source !== expectedSource) throw new Error('写入响应格式或数据源不兼容');
}
