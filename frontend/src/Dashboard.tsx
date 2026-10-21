import { React } from './platform/react-host';
import { filtersSchema, preview, useResource, type Filters, type Selection } from './services/preview';
import { ResourceState } from './components/common';
import { Select } from './components/Select';
import { InfoTip, MaterialIcon } from './components/InfoTip';
import { CollectionDetails } from './components/CollectionDetails';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { RecordsPage } from './pages/RecordsPage';
import { PeoplePage } from './pages/PeoplePage';
import { ModelsPage } from './pages/ModelsPage';

const pages = [
  { id: 'overview', label: '概览', icon: 'dashboard' }, { id: 'usage', label: '使用分析', icon: 'analytics' },
  { id: 'mcp', label: 'MCP 分析', icon: 'link' }, { id: 'requests', label: '用量明细', icon: 'share' },
  { id: 'sessions', label: '对话审计', icon: 'chat_bubble' }, { id: 'people', label: '人员设置', icon: 'group' },
  { id: 'models', label: '模型设置', icon: 'settings' },
];
type PageId = 'overview' | 'usage' | 'mcp' | 'requests' | 'sessions' | 'people' | 'models';
const knownPage = (value: string | null): PageId => pages.some((page) => page.id === value) ? value as PageId : 'overview';

function dateRange(days: number, anchor = '2026-10-15') {
  const day = new Date(`${anchor}T00:00:00Z`);
  const end = new Date(day); end.setUTCDate(day.getUTCDate() + 1);
  day.setUTCDate(day.getUTCDate() - days + 1);
  return { start: day.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10), all_time: false };
}

function MockPages({ page, selection, filters, search, drill, refreshFilters }: { page: PageId; selection: Selection; filters: Filters; search: string; drill: (dimension: string, id: string) => void; refreshFilters: () => void }) {
  if (page === 'overview' || page === 'usage' || page === 'mcp') return <AnalyticsPage page={page} selection={selection} drill={drill} historyAllowed={filters.role === 'admin'} />;
  if (page === 'requests' || page === 'sessions') return <RecordsPage key={`${page}:${search}`} kind={page} selection={selection} filters={filters} initialSearch={search} />;
  if (page === 'people') return <PeoplePage refreshFilters={refreshFilters} />;
  return <ModelsPage />;
}

export function Dashboard({ live = false, ready = false }: { live?: boolean; ready?: boolean }) {
  const params = new URLSearchParams(window.location.search);
  const [page, setPage] = React.useState<PageId>(() => knownPage(params.get('hum_page')));
  const anchor = live ? new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(new Date()) : '2026-10-15';
  const [selection, setSelection] = React.useState<Selection>(() => ({ ...dateRange(7, anchor), department_id: params.get('hum_department') ?? '', user_id: params.get('hum_user') ?? '', server_id: '' }));
  const [search, setSearch] = React.useState('');
  const [drawer, setDrawer] = React.useState(false);
  const [range, setRange] = React.useState('7');
  const [customStart, setCustomStart] = React.useState(selection.start);
  const [customEnd, setCustomEnd] = React.useState(anchor);
  const [dateError, setDateError] = React.useState('');
  const [role, setRole] = React.useState(live ? 'unavailable' : (params.get('role') ?? 'admin'));
  const permitted = (id: string) => !((id === 'people' || id === 'models') && role !== 'admin') && !(id === 'sessions' && !['admin', 'auditor'].includes(role));
  React.useEffect(() => {
    const listener = () => { const next = new URLSearchParams(window.location.search); setPage(knownPage(next.get('hum_page'))); setSelection((value) => ({ ...value, department_id: next.get('hum_department') ?? '', user_id: next.get('hum_user') ?? '' })); setSearch(''); };
    window.addEventListener('popstate', listener); return () => window.removeEventListener('popstate', listener);
  }, []);
  function navigate(id: PageId, next = selection, term = '') {
    if (id === 'overview' || id === 'mcp') next = { ...next, department_id: '', user_id: '' };
    if (id !== 'mcp') next = { ...next, server_id: '' };
    if (id === 'usage') next = { ...next, user_id: '' };
    setPage(id); setSelection(next); setSearch(term); setDrawer(false);
    const url = new URL(window.location.href); url.searchParams.set('hum_page', id);
    for (const [key, value] of Object.entries({ hum_department: next.department_id, hum_user: next.user_id })) { if (value) url.searchParams.set(key, value); else url.searchParams.delete(key); }
    window.history.pushState({}, '', url);
  }
  const title = pages.find((item) => item.id === page)?.label ?? '概览';
  const pageNotes: Record<PageId, string> = {
    overview: '统计展示当前筛选范围内的已知部分，未知用量和费用不会被当作零。',
    usage: '部门筛选会联动趋势、分布和排行，点击图表可筛选用量明细。',
    mcp: '滚动排行榜可查看所有工具；展开工具详情可查看服务、失败次数和耗时。',
    requests: '输入列为未命中缓存的输入量；缺失字段显示 —。点击请求时间查看详情。',
    sessions: '点击会话 ID 查看详情。详情为补充设计，支持连续工具调用分组展开。',
    people: '迁移会改变用户的主部门，历史请求的部门快照保持不变。修改保存在当前 SQLite 数据库。',
    models: '价格变更不回改历史请求费用。价格按 USD / 百万 Tokens。起止日期均包含，按 Asia/Shanghai 判断；结束日期留空为长期有效。同模型启用区间不可重叠。待设置价格按调用日期列出未覆盖区间；已设置价格可编辑。修改保存在当前 SQLite 数据库。',
  };
  return <section className="hum-root" aria-label="用量管理"><div className="hum-mobile-bar"><b>用量管理</b><button className="hum-outline" aria-expanded={drawer} aria-controls="hum-navigation" onClick={() => setDrawer(!drawer)}>{drawer ? '收起导航' : '打开导航'}</button></div>
    <aside className={`hum-sidebar ${drawer ? 'hum-sidebar-open' : ''}`} id="hum-navigation"><nav aria-label="用量管理导航"><p className="hum-nav-label">数据</p>{pages.map((item, index) => <React.Fragment key={item.id}>{index === 5 && <><hr /><p className="hum-nav-label">配置</p></>}<button className={page === item.id ? 'hum-nav-active' : ''} aria-current={page === item.id ? 'page' : undefined} disabled={!permitted(item.id)} onClick={() => navigate(item.id as PageId)}><MaterialIcon name={item.icon} />{item.label}</button></React.Fragment>)}</nav></aside>
    <main className="hum-content"><div className="hum-page-heading"><div className="hum-title"><h1>{title}</h1><InfoTip key={page} label={`${title}说明`}><p>{pageNotes[page]}</p>{!live ? <p>模拟范围：3 个 Profile · 虚构人员 · Asia/Shanghai · 固定基准日 2026-10-15</p> : <p>统计范围为当前配置数据库。</p>}</InfoTip></div><span className="hum-badge">{live ? '实时数据' : '模拟数据'}</span></div>
      {ready && !['people', 'models'].includes(page) && <CollectionDetails selection={selection} />}
      {!ready ? <div className="hum-empty"><h2>业务数据尚未接入</h2><p>存储或业务接口不可用，请检查插件数据路径和身份适配配置。</p><p>不会回退到模拟统计。采集需在测试 Hermes 中显式启用。</p></div> : <MockWorkspace page={page} selection={selection} setSelection={setSelection} search={search} navigate={navigate} permitted={permitted(page)} setRole={setRole} range={range} setRange={setRange} customStart={customStart} setCustomStart={setCustomStart} customEnd={customEnd} setCustomEnd={setCustomEnd} dateError={dateError} setDateError={setDateError} />}
    </main>
  </section>;
}

type WorkspaceProps = {
  page: PageId; selection: Selection; setSelection: (value: Selection) => void; search: string;
  navigate: (page: PageId, selection?: Selection, search?: string) => void; permitted: boolean; setRole: (value: string) => void;
  range: string; setRange: (value: string) => void; customStart: string; setCustomStart: (value: string) => void;
  customEnd: string; setCustomEnd: (value: string) => void; dateError: string; setDateError: (value: string) => void;
};
function MockWorkspace(props: WorkspaceProps) {
  const { page, selection, setSelection, navigate } = props;
  const resource = useResource('/filters', filtersSchema);
  const [updatedFilters, setUpdatedFilters] = React.useState<Filters | null>(null);
  const filters = updatedFilters ?? resource.data;
  React.useEffect(() => { if (filters) props.setRole(filters.role); }, [filters, props.setRole]);
  if (!props.permitted) return <div className="hum-empty" role="alert">无权访问此页面 · 模拟角色权限限制</div>;
  if (!filters) return <ResourceState {...resource} />;
  const showFilters = !['people', 'models'].includes(page);
  function drill(dimension: string, id: string) {
    const next = { ...selection, department_id: dimension === 'department' ? id : selection.department_id, user_id: dimension === 'user' ? id : '', server_id: '' };
    navigate('requests', next, dimension === 'model' || dimension === 'provider' ? id : '');
  }
  return <>
    {showFilters && <div className="hum-filterbar">
      {page !== 'overview' && page !== 'mcp' && <><Select className="hum-select-filled" label="部门筛选" value={selection.department_id} onChange={(value) => setSelection({ ...selection, department_id: value, user_id: '' })} options={[{ value: '', label: '全部部门' }, ...filters.departments.map((item) => ({ value: item.id, label: item.name }))]} />
        {(page === 'requests' || page === 'sessions') && <Select className="hum-select-filled" label="人员筛选" value={selection.user_id} onChange={(value) => setSelection({ ...selection, user_id: value })} options={[{ value: '', label: '全部人员' }, ...filters.users.filter((item) => !selection.department_id || item.department_id === selection.department_id).map((item) => ({ value: item.id, label: item.name }))]} />}</>}
      {page === 'mcp' && <Select className="hum-select-filled" label="MCP 服务筛选" value={selection.server_id} onChange={(value) => setSelection({ ...selection, server_id: value })} options={[{ value: '', label: '全部服务' }, ...filters.servers.map((item) => ({ value: item.id, label: item.name }))]} />}
      <div className="hum-date-controls"><Select className="hum-select-filled" label="日期范围" value={props.range} onChange={(value) => { props.setRange(value); props.setDateError(''); if (value !== 'custom') setSelection({ ...selection, ...dateRange(value === 'all' ? 7 : Number(value), filters.anchor), all_time: value === 'all' }); }} options={[{ value: '1', label: '今天' }, { value: '7', label: '近 7 天' }, { value: '30', label: '近 30 天' }, { value: '90', label: '近 90 天' }, { value: '180', label: '近半年' }, { value: '365', label: '近一年' }, { value: 'all', label: '所有时间' }, { value: 'custom', label: '自定义' }]} />
        {props.range === 'custom' && <><input aria-label="开始日期" type="date" value={props.customStart} onChange={(event) => props.setCustomStart(event.target.value)} /><input aria-label="结束日期" type="date" value={props.customEnd} onChange={(event) => props.setCustomEnd(event.target.value)} /><button onClick={() => { const start = new Date(`${props.customStart}T00:00:00Z`); const end = new Date(`${props.customEnd}T00:00:00Z`); const days = (end.getTime() - start.getTime()) / 86400000; if (!Number.isFinite(days) || days < 0 || days >= 366) { props.setDateError('请选择有效的日期范围（最多 366 天）'); return; } end.setUTCDate(end.getUTCDate() + 1); props.setDateError(''); setSelection({ ...selection, start: props.customStart, end: end.toISOString().slice(0, 10), all_time: false }); }}>应用</button></>}
      </div><button className="hum-text" onClick={() => { props.setRange('7'); props.setDateError(''); navigate(page, { ...dateRange(7, filters.anchor), department_id: '', user_id: '', server_id: '' }); }}>清除筛选</button>
    </div>}{props.dateError && <p role="alert">{props.dateError}</p>}
    <MockPages page={page} selection={selection} filters={filters} search={props.search} drill={drill} refreshFilters={() => { void preview('/filters', filtersSchema).then((result) => setUpdatedFilters(result.data)).catch(() => resource.retry()); }} />
  </>;
}
