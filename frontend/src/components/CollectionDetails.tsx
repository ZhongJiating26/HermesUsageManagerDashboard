import { z } from 'zod';
import { React } from '../platform/react-host';
import { query, useResource, type Selection } from '../services/preview';
import { number, ResourceState, time } from './common';

const qualitySchema = z.object({
  collection: z.object({ status: z.string(), last_success: z.string().nullable(), profile_configured: z.number(), profile_connected: z.number(), pending: z.number(), failed: z.number(), dropped: z.number(), invalid: z.number(), unavailable_hooks: z.string().array() }),
  window: z.object({ requests: z.number(), unresolved_identity: z.number(), missing_usage: z.number(), missing_cache: z.number(), unknown_cost: z.number(), unclassified_tools: z.number(), received_time_tools: z.number() }),
});

export function CollectionDetails({ selection }: { selection: Selection }) {
  const resource = useResource(`/quality?${query(selection)}`, qualitySchema);
  if (!resource.data) return <details className="hum-quality" aria-label="采集状态与数据质量"><summary>{resource.loading ? '正在读取采集状态…' : '采集状态暂不可用'}<span className="hum-quality-toggle">查看详情</span></summary><div aria-label="数据质量详情"><ResourceState {...resource} /></div></details>;
  const { collection, window } = resource.data;
  const status = ({ observed: '已收到采集数据', registered: '等待采集数据', degraded: '采集状态需检查', unavailable: '尚无采集数据' } as Record<string, string>)[collection.status] ?? '采集状态未知';
  const incomplete = window.unresolved_identity + window.missing_usage + window.missing_cache + window.unknown_cost + window.unclassified_tools > 0 || collection.unavailable_hooks.length > 0;
  return <details className="hum-quality" aria-label="采集状态与数据质量"><summary>{status} · 当前范围 {number(window.requests)} 条请求{incomplete ? ' · 部分信息待完善' : ''}<span className="hum-quality-toggle">查看详情</span></summary><div aria-label="数据质量详情"><h3>采集与数据质量</h3><p>采集：{collection.status} · 当前库 Profile 心跳 {collection.profile_connected}/{collection.profile_configured}</p>{collection.unavailable_hooks.length > 0 && <p>辅助调用 Hook 不可用，辅助用量未采集，不计为零。</p>}<p>最后入库：{collection.last_success ? time(collection.last_success) : '尚无采集记录'}</p><p>队列：待处理 {collection.pending} · 隔离 {collection.failed} · 丢弃 {collection.dropped} · 无效 {collection.invalid}</p><p>当前筛选范围：请求 {number(window.requests)} · 身份未知 {window.unresolved_identity} · 用量缺失 {window.missing_usage} · 缓存未知 {window.missing_cache} · 费用未知 {window.unknown_cost} · 工具分类未知 {window.unclassified_tools} · 工具按接收时间 {window.received_time_tools}</p><p>仅统计当前数据库中的已知部分，未知用量与费用不计为零；未连接的 Profile 不包含在内。</p><button className="hum-text" onClick={resource.retry}>刷新数据质量</button></div></details>;
}
