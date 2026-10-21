import { React } from '../platform/react-host';
import { analyticsSchema, query, useResource, type Selection, type Distribution } from '../services/preview';
import { EChart, type ChartOption } from '../components/EChart';
import { departmentOption, pieOption, rankOption, trendOption } from '../components/chart-options';
import { tokens, million, Empty, money, ResourceState } from '../components/common';
import { InfoTip } from '../components/InfoTip';
import { HistoryRanking } from '../components/HistoryRanking';

type Drill = (dimension: string, id: string) => void;
function ChartCard({ title, rows, kind = 'pie', drill, dimension }: { title: string; rows: Distribution[]; kind?: 'pie' | 'department'; drill: Drill; dimension: string }) {
  const [metric, setMetric] = React.useState<'tokens' | 'cost'>('tokens');
  const option = kind === 'pie' ? pieOption(rows, metric) : departmentOption(rows, metric);
  const total = rows.reduce((sum, row) => sum + (row[metric] ?? 0), 0);
  return <section className="hum-card"><div className="hum-card-head"><div className="hum-title"><h2>{title}</h2><InfoTip label={`${title}说明`}>点击图表可筛选明细。{metric === 'cost' ? '仅已知价格的估算费用，未知费用未计入。' : '图表按 M Token 展示已知用量，缺失细分不作零值推断。'}</InfoTip></div><div className="hum-segment" aria-label={`${title}统计指标`}>
    <button aria-pressed={metric === 'tokens'} onClick={() => setMetric('tokens')}>M Token</button><button aria-pressed={metric === 'cost'} onClick={() => setMetric('cost')}>费用</button></div></div>
    {total > 0 ? <EChart label={`${title} · ${metric === 'cost' ? '已知估算费用 USD' : 'Tokens'}`} option={option} onClick={(event) => { const row = rows.find((item) => item.name === event.name); if (row) drill(dimension, row.id); }} /> : <Empty text="该维度暂无已知数值" />}
    <details className="hum-chart-data"><summary>查看数据 / 筛选明细</summary><ul>{rows.map((row) => <li key={row.id}><button className="hum-text" onClick={() => drill(dimension, row.id)}>{row.name}</button><span>{metric === 'tokens' ? tokens(row.tokens) : money(row.cost)}</span></li>)}</ul></details>
  </section>;
}

export function AnalyticsPage({ page, selection, drill, historyAllowed = false }: { page: 'overview' | 'usage' | 'mcp'; selection: Selection; drill: Drill; historyAllowed?: boolean }) {
  const resource = useResource(`/overview/summary?${query(selection)}`, analyticsSchema);
  if (resource.loading || resource.error) return <ResourceState {...resource} />;
  const data = resource.data;
  if (!data) return <Empty />;
  if (page === 'mcp' ? data.tools.length === 0 : data.count === 0 && data.kpis.active === 0) return <><Empty />{page !== 'mcp' && selection.all_time && historyAllowed && <HistoryRanking selection={selection} />}</>;
  const kpis = data.kpis;
  const total = kpis.total_tokens;
  const rankedUsers = [...data.distributions.user].sort((first, second) => (second.tokens ?? 0) - (first.tokens ?? 0)).slice(0, 10);
  const mcpOption: ChartOption = { ...rankOption(data.tools.map((item) => ({ name: item.name, value: item.calls })), 'calls'), tooltip: {
    trigger: 'axis', renderMode: 'richText', confine: true, formatter: (params: unknown) => {
      const item = Array.isArray(params) ? params[0] : params;
      const name = item && typeof item === 'object' && 'name' in item ? String(item.name) : '';
      const tool = data.tools.find((entry) => entry.name === name);
      return tool ? `${tool.name}\n接口标识：${tool.id}\n服务：${tool.server_id}\n调用：${tool.calls} 次 · 失败：${tool.failed} 次\n平均耗时：${tool.duration_ms} ms` : name;
    },
  } };
  return <div className="hum-stack"><p className="hum-caption">统计卡片、分布图和逐次排行仅含当前采集库中的已知用量；历史汇总单独展示。用量单位为 M Token（百万 Token）。</p>
    {page === 'overview' && <div className="hum-kpis">
      <section><h2>用量 · M Token</h2><strong>{million(total, 2)}<small> M Token</small></strong>{([['输入（未命中缓存）', kpis.input], ['输入（命中缓存）', kpis.cached], ['输出', kpis.output]] as const).map(([label, value]) => <div className="hum-kpi-line" key={label}><span>{label}</span><span>{tokens(value)}</span>{value != null && <meter min={0} max={total || 1} value={value} />}</div>)}</section>
      <section><h2>费用 · 已知部分估算</h2><strong>{money(kpis.cost)} <small>USD</small></strong>{([['输入（未命中缓存）', kpis.input_cost], ['输入（命中缓存）', kpis.cached_cost], ['输出', kpis.output_cost]] as const).map(([label, value]) => <div className="hum-kpi-line" key={label}><span>{label}</span><span>{money(value)}</span>{value != null && <meter min={0} max={kpis.cost || 1} value={value} />}</div>)}</section>
      <section className="hum-active"><div><h2>活跃人数</h2><strong>{kpis.active}<small> 人</small></strong></div><div><h2>主力模型</h2><b>{kpis.primary_model ?? '—'}</b></div></section>
    </div>}
    <section className="hum-card"><div className="hum-title"><h2>{page === 'mcp' ? 'MCP 调用次数' : 'Token 消耗 / 活跃人数'}</h2><InfoTip label="用量数据说明">{page === 'mcp' ? '仅统计已确认属于 MCP 的工具调用，单位为次。' : `数据质量：${kpis.unknown_cache} 条请求缓存细分未知；${kpis.unknown_cost} 条请求费用未知。图表展示已知部分。`}</InfoTip></div><EChart option={trendOption(data, page)} label={page === 'mcp' ? 'MCP 调用趋势' : 'Token 与活跃人数趋势'} height={320} /></section>
    {page === 'overview' && <div className="hum-grid"><ChartCard title="部门 Tokens" kind="department" rows={data.distributions.department} dimension="department" drill={drill} /><ChartCard title="部门分布" rows={data.distributions.department} dimension="department" drill={drill} /><ChartCard title="模型分布" rows={data.distributions.model} dimension="model" drill={drill} /><ChartCard title="提供商分布" rows={data.distributions.provider} dimension="provider" drill={drill} /></div>}
    {page === 'usage' && <div className="hum-grid"><ChartCard title="人员用量" rows={data.distributions.user} dimension="user" drill={drill} /><ChartCard title="模型用量" rows={data.distributions.model} dimension="model" drill={drill} /></div>}
    {page !== 'mcp' && selection.all_time && historyAllowed && <HistoryRanking selection={selection} />}
    {page !== 'mcp' ? <section className="hum-card"><h2>逐次采集用户排行 · Top 10</h2><p className="hum-caption">仅统计当前筛选范围内已采集的请求，不代表完整 Hermes 历史用量。</p><EChart label="用户 Tokens 排行" height={360} option={rankOption(rankedUsers.map((item) => ({ name: item.name, value: item.tokens })))} onClick={(event) => { const user = rankedUsers[event.dataIndex]; if (user) drill('user', user.id); }} /><details className="hum-chart-data"><summary>查看排行 / 筛选明细</summary><ul>{rankedUsers.map((item) => <li key={item.id}><button className="hum-text" onClick={() => drill('user', item.id)}>{item.name}</button><span>{tokens(item.tokens)}</span></li>)}</ul></details></section>
      : <section className="hum-card"><div className="hum-title"><h2>接口调用排行榜</h2><InfoTip label="接口调用排行榜说明">滚动图表查看所有工具；展开下表查看服务、失败与耗时信息。</InfoTip></div><EChart label="MCP 工具调用排行，可滚动查看全部工具" height={480} option={mcpOption} /><details className="hum-chart-data"><summary>全部工具详情（{data.tools.length}）</summary><div className="hum-table-scroll"><table><thead><tr><th>接口</th><th>稳定标识</th><th>服务</th><th>次数</th><th>失败</th><th>平均耗时</th></tr></thead><tbody>{data.tools.map((tool) => <tr key={tool.id}><td>{tool.name}</td><td>{tool.id}</td><td>{tool.server_id}</td><td>{tool.calls}</td><td>{tool.failed}</td><td>{tool.duration_ms} ms</td></tr>)}</tbody></table></div></details></section>}
  </div>;
}
