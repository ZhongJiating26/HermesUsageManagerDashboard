import { React } from '../platform/react-host';
import { departmentSchema, userSchema, mutate, useResource, type Department, type User } from '../services/preview';
import { Empty, Modal, Pagination, ResourceState, useDebounce } from '../components/common';
import { Select } from '../components/Select';

const departmentsSchema = departmentSchema.array();
const usersSchema = userSchema.array();
type Editor = { kind: 'department'; item?: Department } | { kind: 'user'; item?: User };
type Confirmation = { title: string; text: string; action: () => Promise<void> };

export function PeoplePage({ refreshFilters }: { refreshFilters: () => void }) {
  const [tab, setTab] = React.useState('users');
  const [revision, setRevision] = React.useState(0);
  const departments = useResource('/people/departments', departmentsSchema, revision);
  const users = useResource('/people/users', usersSchema, revision);
  const [search, setSearch] = React.useState('');
  const term = useDebounce(search);
  const [department, setDepartment] = React.useState('__all__');
  const [editorDepartment, setEditorDepartment] = React.useState('');
  const [page, setPage] = React.useState(1);
  const [size, setSize] = React.useState(20);
  const [editor, setEditor] = React.useState<Editor | null>(null);
  const [confirmation, setConfirmation] = React.useState<Confirmation | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState('');
  const [left, setLeft] = React.useState('');
  const [right, setRight] = React.useState('__initial__');
  const [leftSearch, setLeftSearch] = React.useState('');
  const [rightSearch, setRightSearch] = React.useState('');
  const [leftIds, setLeftIds] = React.useState<string[]>([]);
  const [rightIds, setRightIds] = React.useState<string[]>([]);
  React.useEffect(() => { setPage(1); }, [term, department, tab, size]);
  React.useEffect(() => {
    if (departments.data) {
      if (left && !departments.data.some((item) => item.id === left)) setLeft('');
      if (right && !departments.data.some((item) => item.id === right)) setRight(departments.data[0]?.id ?? '');
    }
  }, [departments.data, left, right]);
  async function execute(action: () => Promise<void>) {
    setBusy(true); setError(null);
    try {
      await action();
      setEditor(null); setConfirmation(null); setRevision((value) => value + 1); refreshFilters();
      setLeftIds([]); setRightIds([]); setNotice('修改已保存到 SQLite');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '保存失败'); }
    finally { setBusy(false); }
  }
  if (departments.loading || users.loading || departments.error || users.error) return <ResourceState loading={departments.loading || users.loading} error={departments.error || users.error} retry={() => { departments.retry(); users.retry(); }} />;
  const allDepartments = departments.data ?? [];
  const allUsers = users.data ?? [];
  const departmentOptions = [{ value: '', label: '未分配部门' }, ...allDepartments.map((item) => ({ value: item.id, label: item.name }))];
  const visible = allUsers.filter((user) => (department === '__all__' || user.department_id === department) && `${user.name} ${user.external_id}`.toLowerCase().includes(term.toLowerCase()));
  const departmentName = (id: string) => allDepartments.find((item) => item.id === id)?.name ?? '未分配部门';
  const openEditor = (value: Editor) => { setEditor(value); setEditorDepartment(value.kind === 'user' ? value.item?.department_id ?? '' : ''); setError(null); };
  const ask = (value: Confirmation) => { setConfirmation(value); setError(null); };
  function assignment(side: 'left' | 'right') {
    const selectedDepartment = side === 'left' ? left : right;
    const selectedIds = side === 'left' ? leftIds : rightIds;
    const setIds = side === 'left' ? setLeftIds : setRightIds;
    const value = side === 'left' ? leftSearch : rightSearch;
    const matches = allUsers.filter((user) => user.department_id === selectedDepartment && `${user.name} ${user.external_id}`.includes(value));
    const label = side === 'left' ? '左侧' : '右侧';
    return <div className="hum-assignment-side"><Select label={`${label}部门`} value={selectedDepartment} options={departmentOptions} onChange={(value) => { (side === 'left' ? setLeft : setRight)(value); setIds([]); }} />
      <div className="hum-assignment-list"><div className="hum-assignment-search"><input type="checkbox" aria-label={`${label}全选`} checked={matches.length > 0 && matches.every((user) => selectedIds.includes(user.id))} onChange={(event) => setIds(event.target.checked ? matches.map((user) => user.id) : [])} /><span>({matches.length})</span><input aria-label={`${label}搜索用户`} placeholder="搜索用户" value={value} onChange={(event) => (side === 'left' ? setLeftSearch : setRightSearch)(event.target.value)} /></div>
        {matches.length === 0 && <Empty text="该部门暂无匹配成员" />}{matches.map((user) => <label className="hum-person" key={user.id}><input type="checkbox" checked={selectedIds.includes(user.id)} onChange={(event) => setIds(event.target.checked ? [...selectedIds, user.id] : selectedIds.filter((id) => id !== user.id))} /><span>{user.name}</span><small>{user.id}</small></label>)}
      </div></div>;
  }
  return <div className="hum-stack"><div className="hum-toolbar"><div className="hum-tabs" role="tablist" aria-label="人员设置分类">{[['users', '用户列表'], ['departments', '部门列表'], ['assignment', '部门分配']].map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>{label}</button>)}</div>
    {tab === 'users' && <><Select label="人员部门筛选" value={department} onChange={setDepartment} options={[{ value: '__all__', label: '全部部门' }, ...departmentOptions]} /><input className="hum-search" aria-label="搜索用户" placeholder="搜索用户 / Open ID" value={search} onChange={(event) => setSearch(event.target.value)} /><button onClick={() => openEditor({ kind: 'user' })}>＋ 新增映射</button></>}
    {tab === 'departments' && <button onClick={() => openEditor({ kind: 'department' })}>⊕ 新建部门</button>}</div>
    {notice && <p className="hum-notice" role="status">{notice}</p>}
    {tab === 'users' && (visible.length ? <><div className="hum-table-scroll"><table><thead><tr><th>飞书 open_id</th><th>用户</th><th>部门</th><th>Profile</th><th>操作</th></tr></thead><tbody>{visible.slice((page - 1) * size, page * size).map((user) => <tr key={user.id}><td>{user.external_id}</td><td>{user.name}</td><td>{departmentName(user.department_id)}</td><td>{user.profile}</td><td><button className="hum-text" onClick={() => openEditor({ kind: 'user', item: user })} aria-label={`编辑用户 ${user.name}`}>编辑</button></td></tr>)}</tbody></table></div><Pagination page={page} size={size} total={visible.length} onPage={setPage} onSize={setSize} /></> : <Empty />)}
    {tab === 'departments' && <div className="hum-table-scroll"><table><thead><tr><th>部门</th><th>人数</th><th>操作</th></tr></thead><tbody>{allDepartments.map((item) => <tr key={item.id}><td>{item.name}</td><td>{allUsers.filter((user) => user.department_id === item.id).length}</td><td><button className="hum-text" aria-label={`删除部门 ${item.name}`} onClick={() => ask({ title: '删除部门', text: `确认删除“${item.name}”？含成员的部门会被阻止删除。`, action: () => mutate(`/people/departments/${item.id}`, 'DELETE') })}>删除</button><button className="hum-text" aria-label={`编辑部门 ${item.name}`} onClick={() => openEditor({ kind: 'department', item })}>编辑</button></td></tr>)}</tbody></table></div>}
    {tab === 'assignment' && <div className="hum-assignment">{assignment('left')}<div className="hum-move-actions"><button disabled={!rightIds.length || left === right} onClick={() => ask({ title: '确认部门迁移', text: `将 ${rightIds.length} 人迁移到“${departmentName(left)}”？`, action: () => mutate('/people/assignments/move', 'POST', { user_ids: rightIds, department_id: left }) })}>← 移到左侧 ({rightIds.length})</button><button disabled={!leftIds.length || left === right} onClick={() => ask({ title: '确认部门迁移', text: `将 ${leftIds.length} 人迁移到“${departmentName(right)}”？`, action: () => mutate('/people/assignments/move', 'POST', { user_ids: leftIds, department_id: right }) })}>移到右侧 ({leftIds.length}) →</button>{left === right && <small>两侧部门相同，不能迁移</small>}</div>{assignment('right')}</div>}
    {editor && <Modal title={editor.kind === 'department' ? (editor.item ? '编辑部门' : '新建部门') : (editor.item ? '编辑用户映射' : '新增用户映射')} onClose={() => { if (!busy) setEditor(null); }}><form className="hum-form" onSubmit={(event) => {
      event.preventDefault(); const values = new FormData(event.currentTarget); const name = String(values.get('name') ?? '').trim();
      if (editor.kind === 'department') void execute(() => mutate(`/people/departments${editor.item ? `/${editor.item.id}` : ''}`, editor.item ? 'PATCH' : 'POST', { name }));
      else void execute(() => mutate(`/people/users${editor.item ? `/${editor.item.id}` : ''}`, editor.item ? 'PATCH' : 'POST', { name, external_id: values.get('external_id'), department_id: values.get('department_id'), profile: values.get('profile'), platform: editor.item?.platform ?? 'feishu' }));
    }}><label>名称<input name="name" required maxLength={50} defaultValue={editor.item?.name ?? ''} /></label>{editor.kind === 'user' && <><label>Open ID<input name="external_id" required maxLength={100} defaultValue={editor.item?.external_id ?? ''} /></label><div className="hum-form-field"><span>主部门</span><Select label="主部门" name="department_id" value={editorDepartment} onChange={setEditorDepartment} options={departmentOptions} /></div><label>Profile<input name="profile" required defaultValue={editor.item?.profile ?? 'profile-1'} /></label></>}{error && <p role="alert">{error}</p>}<div className="hum-form-actions"><button type="button" className="hum-outline" disabled={busy} onClick={() => setEditor(null)}>取消</button><button disabled={busy}>{busy ? '保存中…' : '保存'}</button></div></form></Modal>}
    {confirmation && <Modal title={confirmation.title} onClose={() => { if (!busy) setConfirmation(null); }}><p>{confirmation.text}</p>{error && <p role="alert">{error}</p>}<div className="hum-form-actions"><button className="hum-outline" disabled={busy} onClick={() => setConfirmation(null)}>取消</button><button disabled={busy} onClick={() => void execute(confirmation.action)}>{busy ? '处理中…' : '确认'}</button></div></Modal>}
  </div>;
}
