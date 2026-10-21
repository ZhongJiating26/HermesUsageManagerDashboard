import { React } from '../platform/react-host';
import { query, requestSchema, sessionSchema, useResource, type Filters, type ModelRequest, type Selection, type Session } from '../services/preview';
import { Empty, Modal, money, number, million, tokens, Pagination, ResourceState, time } from '../components/common';
import { SessionDetails } from '../components/SessionDetails';

const requestsSchema = requestSchema.array();
const sessionsSchema = sessionSchema.array();

export function RecordsPage({ kind, selection, filters, initialSearch = '' }: { kind: 'requests' | 'sessions'; selection: Selection; filters: Filters; initialSearch?: string }) {
  const [page, setPage] = React.useState(1);
  const [size, setSize] = React.useState(20);
  const [sort, setSort] = React.useState('time');
  const [order, setOrder] = React.useState('desc');
  const term = initialSearch;
  const [detail, setDetail] = React.useState<ModelRequest | Session | null>(null);
  const schema = kind === 'requests' ? requestsSchema : sessionsSchema;
  const resource = useResource<(ModelRequest | Session)[]>(`/${kind}?${query(selection, { page, page_size: size, sort, order, search: term })}`, schema);
  React.useEffect(() => { setPage(1); }, [selection, term, size, kind]);
  const names = (id: string, type: 'department' | 'user') => (type === 'department' ? filters.departments : filters.users).find((item) => item.id === id)?.name ?? '未归属';
  const changeSort = (field: string) => { setSort(field); setOrder(sort === field && order === 'desc' ? 'asc' : 'desc'); setPage(1); };
  return <div className="hum-stack">
    <ResourceState {...resource} />
    {!resource.loading && !resource.error && resource.data && (resource.data.length === 0 ? <Empty /> : <><div className="hum-table-scroll hum-record-table"><table><thead><tr>
      <th><button className="hum-text" onClick={() => changeSort('time')}>{kind === 'requests' ? '请求时间' : '会话 ID'} {sort === 'time' ? (order === 'desc' ? '↓' : '↑') : '↕'}</button></th><th>部门</th><th>用户</th><th>{kind === 'requests' ? '模型' : '对话开始时间'}</th>
      <th><button className="hum-text" onClick={() => changeSort('input')}>输入 ↕</button><small> M Token</small></th><th><button className="hum-text" onClick={() => changeSort('output')}>输出 ↕</button><small> M Token</small></th><th>缓存读取<small> M Token</small></th><th>{kind === 'requests' ? '耗时' : 'MCP 使用'}</th>
    </tr></thead><tbody>{resource.data.map((row) => <tr key={row.id}>
      <td><button className="hum-text hum-row-link" onClick={() => setDetail(row)}>{'status' in row && <span className={row.status === 'failed' ? 'hum-failed' : 'hum-success'} aria-label={row.status === 'failed' ? '请求失败' : '请求成功'}>{row.status === 'failed' ? '⊗' : '⊙'}</span>}{kind === 'requests' ? time(row.time) : row.id}</button></td>
      <td>{names(row.department_id, 'department')}</td><td>{names(row.user_id, 'user')}</td><td>{'model' in row ? <span className="hum-model" title={`${row.provider} / ${row.model}`}><b>{row.provider.slice(0, 1)}</b>{row.model}</span> : time(row.time)}</td><td>{million(row.input)}</td><td>{million(row.output)}</td><td>{million(row.cached)}</td><td>{'duration_ms' in row ? `${number(row.duration_ms)} ms` : `${row.mcp_calls} 次`}</td>
    </tr>)}</tbody></table></div><Pagination page={page} total={resource.total} size={size} onPage={setPage} onSize={setSize} /></>)}
    {detail && <Modal drawer={kind === 'sessions'} title={kind === 'requests' ? '请求详情' : '对话详情'} onClose={() => setDetail(null)}>{'model' in detail ? <dl className="hum-detail-grid">{Object.entries({ '请求 ID': detail.id, '会话': detail.session_id, 'Profile': detail.profile, '提供商': detail.provider, '模型': detail.model, '状态': detail.status, '请求时间': time(detail.time), '输入未命中': tokens(detail.input), '缓存读取': tokens(detail.cached), '输出': tokens(detail.output), '费用（估算）': money(detail.cost) }).map(([label, value]) => <React.Fragment key={label}><dt>{label}</dt><dd>{value}</dd></React.Fragment>)}</dl> : <SessionDetails key={detail.id} session={detail} filters={filters} selection={selection} />}</Modal>}
  </div>;
}
