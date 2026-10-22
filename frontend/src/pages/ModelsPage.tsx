import { React } from '../platform/react-host';
import { mutate, priceSchema, unpricedSchema, useResource, type Price } from '../services/preview';
import { Empty, Modal, number, ResourceState } from '../components/common';

const pricesSchema = priceSchema.array();
const pendingSchema = unpricedSchema.array();

const priceValue = (value: number | null) => value == null ? '未设置' : `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 })}`;

export function ModelsPage() {
  const [revision, setRevision] = React.useState(0);
  const prices = useResource('/models/prices', pricesSchema, revision);
  const pending = useResource('/models/unpriced', pendingSchema, revision);
  const [tab, setTab] = React.useState<'configured' | 'pending'>('configured');
  const [editor, setEditor] = React.useState<Partial<Price> | null>(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [notice, setNotice] = React.useState('');
  function openEditor(value: Partial<Price>) { setEditor(value); setError(''); }
  const resource = tab === 'configured' ? prices : pending;
  return <div className="hum-stack"><div className="hum-toolbar"><div className="hum-tabs" role="tablist" aria-label="模型价格分类">
    <button role="tab" aria-selected={tab === 'configured'} onClick={() => setTab('configured')}>已设置价格{prices.data ? ` (${prices.data.length})` : ''}</button>
    <button role="tab" aria-selected={tab === 'pending'} onClick={() => setTab('pending')}>待设置价格{pending.data ? ` (${pending.data.length})` : ''}</button>
  </div><button onClick={() => openEditor({})}>＋ 新增价格版本</button></div>
    <p>价格单位：美元 / M Token。保存后自动补算生效日期内缺失的历史费用；已有费用保持不变，用量不完整的请求仍显示未知。</p>
    {notice && <p role="status">{notice}</p>}<ResourceState {...resource} />
    {tab === 'configured' && prices.data && (prices.data.length ? <div className="hum-table-scroll"><table><thead><tr><th>提供商</th><th>模型</th><th>输入未命中</th><th>缓存读取</th><th>缓存写入</th><th>输出</th><th>生效开始日期</th><th>生效结束日期</th><th>状态</th><th>操作</th></tr></thead><tbody>{prices.data.map((item) => <tr key={item.id}><td>{item.provider}</td><td>{item.model}</td><td>{priceValue(item.input)}</td><td>{priceValue(item.cached)}</td><td>{priceValue(item.cache_write)}</td><td>{priceValue(item.output)}</td><td>{item.valid_from}</td><td>{item.valid_to ?? '长期有效'}</td><td>{item.enabled ? '启用' : '停用'}</td><td><button className="hum-text" onClick={() => openEditor(item)}>编辑</button><button className="hum-text" onClick={() => openEditor({ ...item, id: undefined, valid_from: '', valid_to: null })}>新增版本</button></td></tr>)}</tbody></table></div> : <Empty text="暂无已设置价格" />)}
    {tab === 'pending' && pending.data && (pending.data.length ? <div className="hum-table-scroll"><table><thead><tr><th>提供商</th><th>模型</th><th>未覆盖开始日期</th><th>未覆盖结束日期</th><th>涉及请求</th><th>原因</th><th>操作</th></tr></thead><tbody>{pending.data.map((item) => <tr key={item.id}><td>{item.provider}</td><td>{item.model}</td><td>{item.valid_from}</td><td>{item.valid_to}</td><td>{number(item.request_count)}</td><td>{item.reason}</td><td><button className="hum-text" onClick={() => openEditor(item.existing_price ?? { provider: item.provider, model: item.model, valid_from: item.valid_from, valid_to: item.valid_to })}>设置价格</button></td></tr>)}</tbody></table></div> : <Empty text="对话中使用的模型均已覆盖价格区间" />)}
    {editor && <Modal title={editor.id ? '编辑价格' : '新增价格版本'} onClose={() => { if (!busy) setEditor(null); }}><form className="hum-form" onSubmit={async (event) => {
      event.preventDefault(); const values = new FormData(event.currentTarget); setError('');
      const start = String(values.get('valid_from'));
      const end = String(values.get('valid_to') ?? '');
      if (end && end < start) { setError('生效结束日期不能早于开始日期'); return; }
      setBusy(true);
      try {
        await mutate(`/models/prices${editor.id ? `/${encodeURIComponent(editor.id)}` : ''}`, editor.id ? 'PATCH' : 'POST', {
          provider: String(values.get('provider')).trim(), model: String(values.get('model')).trim(),
          input: Number(values.get('input')), cached: Number(values.get('cached')), output: Number(values.get('output')), cache_write: String(values.get('cache_write') ?? '').trim() === '' ? null : Number(values.get('cache_write')),
          valid_from: start, valid_to: end || null, enabled: values.get('enabled') === 'on',
        });
        setEditor(null); setRevision((value) => value + 1); setNotice('价格配置已保存，已补算生效日期内可计价的历史缺失费用');
      } catch (reason) { setError(reason instanceof Error ? reason.message : '保存失败'); }
      finally { setBusy(false); }
    }}><label>提供商<input required name="provider" readOnly={Boolean(editor.id)} defaultValue={editor.provider} maxLength={100} /></label><label>模型 ID<input required name="model" readOnly={Boolean(editor.id)} defaultValue={editor.model} maxLength={100} /></label>{(['input', 'cached', 'output'] as const).map((field, index) => <label key={field}>{['输入未命中单价（不含缓存写入）', '缓存命中单价', '输出单价'][index]}<input required type="number" name={field} min={0} step="0.000001" defaultValue={editor[field] ?? 0} /></label>)}<label>缓存写入单价<input type="number" name="cache_write" min={0} step="0.000001" defaultValue={editor.cache_write ?? ''} placeholder="未设置" /></label><p>单价单位：美元 / M Token。缓存写入单独计费，请按供应商实际收费填写；留空时，有写入量的请求费用保持未知。</p><label>生效开始日期<input required type="date" name="valid_from" defaultValue={editor.valid_from} /></label><label>生效结束日期<input type="date" name="valid_to" defaultValue={editor.valid_to ?? ''} /></label><label className="hum-checkbox"><input type="checkbox" name="enabled" defaultChecked={editor.enabled ?? true} />启用</label>{error && <p role="alert">{error}</p>}<div className="hum-form-actions"><button type="button" className="hum-outline" disabled={busy} onClick={() => setEditor(null)}>取消</button><button disabled={busy}>{busy ? '保存中…' : '保存'}</button></div></form></Modal>}
  </div>;
}
