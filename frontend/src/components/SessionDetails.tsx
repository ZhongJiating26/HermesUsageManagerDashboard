import type { z } from 'zod';
import { React } from '../platform/react-host';
import { query, timelineSchema, type Filters, type Selection, type Session } from '../services/preview';
import { useConversation } from '../services/conversation';
import { tokens, Empty, ResourceState, time } from './common';
import { InfoTip } from './InfoTip';

type Message = z.infer<typeof timelineSchema>['messages'][number];

type Attachment = z.infer<typeof timelineSchema>['attachments'][number];
function fileSize(size: number | null) {
  if (size === null) return '大小未知';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
function MessageBubble({ message, files, downloadBase }: { message: Message; files: Attachment[]; downloadBase: (id: string) => string }) {
  const [expanded, setExpanded] = React.useState(false);
  const long = message.text.length > 320 || message.text.split('\n').length > 6;
  return <article className={`hum-message hum-message-${message.kind}`}>
    <div className="hum-message-meta">{message.kind === 'assistant' ? 'Hermes' : '用户'}{message.time && <time dateTime={message.time}>{time(message.time)}</time>}</div>
    {(message.text || files.length === 0) && <div className={`hum-message-bubble${long && !expanded ? ' hum-message-collapsed' : ''}`}><p>{message.text || '—'}</p></div>}
    {files.map((file) => <div className="hum-attachment" key={file.id}>
      <span className="hum-attachment-icon" aria-hidden="true"><svg viewBox="0 0 24 28" fill="none"><path d="M4 1h10l7 7v17a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2Z" stroke="currentColor" strokeWidth="1.5"/><path d="M14 1v7h7M7 15h9M7 20h7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg></span>
      <div className="hum-attachment-info"><strong title={file.name}>{file.name}</strong><small>{fileSize(file.size)} · {file.direction === 'received' ? '用户发送' : '用户接收'} · {file.status === 'ready' ? '快照已保存' : '快照不可用'}</small>{file.status !== 'ready' && <small>{file.status === 'blocked' ? '附件路径不在允许的缓存范围' : '原文件已丢失，无法补备份'}</small>}</div>
      {file.status === 'ready' && <a className="hum-attachment-download" href={downloadBase(file.id)} download aria-label={`下载 ${file.name}`}><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg><span>下载</span></a>}
    </div>)}
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
  const positioned = React.useRef(false);
  const previousHeight = React.useRef(0);
  const previousLoaded = React.useRef(0);
  React.useEffect(() => { positioned.current = false; }, [session.id]);
  React.useLayoutEffect(() => {
    if (data && scroll.current && !positioned.current) {
      scroll.current.scrollTop = scroll.current.scrollHeight;
      positioned.current = true;
    } else if (scroll.current && resource.loaded > previousLoaded.current) {
      scroll.current.scrollTop += scroll.current.scrollHeight - previousHeight.current;
    }
    if (scroll.current) previousHeight.current = scroll.current.scrollHeight;
    previousLoaded.current = resource.loaded;
  }, [data, resource.loaded]);
  React.useEffect(() => {
    if (!resource.hasMore || resource.loading || resource.error || !scroll.current || !sentinel.current) return;
    const observer = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) resource.retry(); }, { root: scroll.current, rootMargin: '100px 0px 0px 0px' });
    observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, [resource.hasMore, resource.loading, resource.error, resource.loaded, resource.retry]);
  return <div className="hum-session-detail">
    <header className="hum-session-summary">
      <div className="hum-title"><h2>{data?.session.title || '对话详情'}</h2><InfoTip label="对话详情说明">默认展示最新消息，向上滚动时读取更早消息；消息数为已加载的原始消息数量，不代表完整会话总数。单次查看最多读取5000条，达到上限会明确提示。MCP 调用为当前筛选范围统计，不等于全部工具调用。缺少标题、消息时间或用量时不补造；工具参数及结果仍遵循现有读取权限。</InfoTip></div>
      <dl className="hum-session-metadata">
        <div className="hum-session-id"><dt>会话 ID</dt><dd>{session.id}</dd></div>
        <div className="hum-session-start"><dt>会话开始时间</dt><dd>{time(data?.session.time || session.time)}</dd></div>
        <div><dt>部门</dt><dd>{filters.departments.find((item) => item.id === session.department_id)?.name ?? '未归属'}</dd></div>
        <div><dt>用户</dt><dd>{filters.users.find((item) => item.id === session.user_id)?.name ?? '未归属'}</dd></div>
        <div><dt>已加载消息</dt><dd>{data ? `${resource.loaded} 条` : '—'}</dd></div>
        <div><dt>MCP 调用</dt><dd>{session.mcp_calls} 次</dd></div>
        <div><dt>输入未命中</dt><dd>{tokens(session.input)}</dd></div>
        <div><dt>输出</dt><dd>{tokens(session.output)}</dd></div>
        <div><dt>缓存读取</dt><dd>{tokens(session.cached)}</dd></div>
        <div><dt>缓存写入</dt><dd>{tokens(session.cache_write)}</dd></div>
      </dl>
    </header>
    <div ref={scroll} className="hum-conversation" role="region" aria-label="对话记录" tabIndex={0} aria-busy={resource.loading}>
      <div ref={sentinel} className="hum-conversation-sentinel" aria-hidden="true" />

      {data && (resource.messages.length === 0 && !resource.hasMore && !resource.loading ? <Empty text="没有可展示的消息" /> : resource.messages.map((message) => message.kind === 'tools' ? <ToolGroup key={message.id} message={message} /> : <MessageBubble key={message.id} message={message} files={data.attachments.filter((file) => file.message === message.id)} downloadBase={(id) => `/api/plugins/hermes-usage-manager/sessions/${encodeURIComponent(session.id)}/attachments/${id}?${query(selection)}`} />))}
      {resource.loading && data ? <div className="hum-conversation-status" role="status">正在加载更多消息…</div> : <ResourceState {...resource} />}
      {resource.capped && <div className="hum-conversation-status" role="status">本次已加载5000条消息，已达到安全查看上限，更早内容尚未加载。</div>}
    </div>
  </div>;
}
