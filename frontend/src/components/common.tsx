import type { ReactNode } from 'react';
import { React } from '../platform/react-host';
import { Select } from './Select';

export const number = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat('zh-CN').format(value);
export const compact = (value: number | null) => value == null ? '—' : new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
export const million = (value: number | null | undefined, precision = 6) => value == null ? '—' : new Intl.NumberFormat('en-US', { maximumFractionDigits: value > 0 && value / 1_000_000 < 10 ** -precision ? 6 : precision }).format(value / 1_000_000);
export const tokens = (value: number | null | undefined) => value == null ? '—' : `${million(value)} M Token`;
export const money = (value: number | null) => value == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(value);
export const time = (value: string) => new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(value));

export function ResourceState({ loading, error, retry }: { loading: boolean; error: string | null; retry: () => void }) {
  if (loading) return <div className="hum-skeleton" role="status" aria-label="加载中"><span /><span /><span /></div>;
  if (error) return <div className="hum-empty" role="alert"><strong>{error.includes('403') ? '无权访问此内容' : '加载失败'}</strong><p>{error}</p><button onClick={retry}>重试</button></div>;
  return null;
}

export function Empty({ text = '当前筛选范围暂无数据' }: { text?: string }) {
  return <div className="hum-empty"><span aria-hidden="true">◌</span><p>{text}</p><small>可调整筛选条件后重试</small></div>;
}

export function Pagination({ page, total, size, onPage, onSize }: { page: number; total: number; size: number; onPage: (page: number) => void; onSize: (size: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size));
  React.useEffect(() => { if (page > pages) onPage(pages); }, [page, pages, onPage]);
  return <div className="hum-pagination"><span>共 {number(total)} 条</span><span>每页</span><Select label="每页条数" value={String(size)} onChange={(value) => onSize(Number(value))} options={[20, 50, 100].map((value) => ({ value: String(value), label: String(value) }))} /><button className="hum-outline" aria-label="上一页" disabled={page <= 1} onClick={() => onPage(page - 1)}>‹</button><span className="hum-page-number">{page}/{pages}</span><button className="hum-outline" aria-label="下一页" disabled={page >= pages} onClick={() => onPage(page + 1)}>›</button></div>;
}

export function Modal({ title, children, onClose, drawer = false }: { title: string; children: ReactNode; onClose: () => void; drawer?: boolean }) {
  const element = React.useRef<HTMLDialogElement>(null);
  const previousFocus = React.useRef<HTMLElement | null>(null);
  React.useEffect(() => {
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    element.current?.showModal();
    const locked: { element: HTMLElement; horizontal: string; vertical: string; horizontalPriority: string; verticalPriority: string; top: number; left: number }[] = [];
    if (drawer) {
      let ancestor = element.current?.parentElement ?? null;
      while (ancestor) {
        const style = getComputedStyle(ancestor);
        if (ancestor === document.body || ancestor === document.documentElement || /auto|scroll/.test(`${style.overflowX} ${style.overflowY}`)) {
          locked.push({ element: ancestor, horizontal: ancestor.style.getPropertyValue('overflow-x'), vertical: ancestor.style.getPropertyValue('overflow-y'), horizontalPriority: ancestor.style.getPropertyPriority('overflow-x'), verticalPriority: ancestor.style.getPropertyPriority('overflow-y'), top: ancestor.scrollTop, left: ancestor.scrollLeft });
          ancestor.style.setProperty('overflow-x', 'hidden', 'important');
          ancestor.style.setProperty('overflow-y', 'hidden', 'important');
        }
        ancestor = ancestor.parentElement;
      }
    }
    return () => {
      element.current?.close();
      for (const saved of locked) {
        if (saved.horizontal) saved.element.style.setProperty('overflow-x', saved.horizontal, saved.horizontalPriority);
        else saved.element.style.removeProperty('overflow-x');
        if (saved.vertical) saved.element.style.setProperty('overflow-y', saved.vertical, saved.verticalPriority);
        else saved.element.style.removeProperty('overflow-y');
        saved.element.scrollTop = saved.top;
        saved.element.scrollLeft = saved.left;
      }
      previousFocus.current?.focus({ preventScroll: true });
    };
  }, [drawer]);
  return <dialog ref={element} className={`hum-dialog hum-root${drawer ? ' hum-session-drawer' : ''}`} aria-label={title} onCancel={onClose}>
    {drawer ? <div className="hum-drawer-top"><button className="hum-drawer-close" aria-label="关闭对话详情" onClick={onClose}><svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="m9 5 7 7-7 7" fill="none" stroke="currentColor" strokeWidth="2" /></svg></button></div> : <div className="hum-dialog-head"><h2>{title}</h2><button className="hum-icon-button" aria-label="关闭弹窗" onClick={onClose}>×</button></div>}{children}
  </dialog>;
}

export function useDebounce(value: string, delay = 250) {
  const [result, setResult] = React.useState(value);
  React.useEffect(() => { const timer = setTimeout(() => setResult(value), delay); return () => clearTimeout(timer); }, [value, delay]);
  return result;
}
