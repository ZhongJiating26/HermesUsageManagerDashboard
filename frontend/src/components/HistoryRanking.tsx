import { z } from 'zod';
import { React } from '../platform/react-host';
import { useResource, type Selection } from '../services/preview';
import { EChart } from './EChart';
import { rankOption } from './chart-options';
import { ResourceState, tokens } from './common';

const schema = z.object({ available: z.boolean(), message: z.string(), source: z.literal('hermes_session_model_usage'),
  users: z.object({ id: z.string(), name: z.string(), tokens: z.number().nullable(), api_calls: z.number(), sessions: z.number(), unknown_rows: z.number() }).array() });

export function HistoryRanking({ selection }: { selection: Selection }) {
  const params = new URLSearchParams({ department_id: selection.department_id, user_id: selection.user_id });
  const resource = useResource(`/history/users?${params}`, schema);
  const data = resource.data;
  const users = data?.users.slice(0, 10) ?? [];
  return <section className="hum-card hum-history-ranking" aria-label="Hermes 历史用量排行">
    <h2>Hermes 历史用量排行 · 所有时间</h2>
    <p className="hum-caption">与上方逐次采集统计分开展示；历史汇总不对应完整的逐次请求明细。</p>
    <ResourceState {...resource} />
    {data && <><p className="hum-caption">{data.message}</p>{data.available && <>
      <EChart label="Hermes 历史用量排行" height={360} option={rankOption(users.map((u) => ({ name: u.name, value: u.tokens })))} />
      <details className="hum-chart-data"><summary>查看历史排行数据</summary><ul>{users.map((u) => <li key={u.id}><span>{u.name}</span><span>{tokens(u.tokens)}{u.unknown_rows > 0 ? '（部分用量未知）' : ''}</span></li>)}</ul></details>
    </>}</>}
  </section>;
}
