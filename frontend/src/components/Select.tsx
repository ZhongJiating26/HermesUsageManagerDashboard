import type { CSSProperties, KeyboardEvent } from 'react';
import { React } from '../platform/react-host';

type Option = { value: string; label: string };

export function Select({ label, value, options, onChange, name, disabled = false, className = '' }: {
  label: string; value: string; options: Option[]; onChange: (value: string) => void;
  name?: string; disabled?: boolean; className?: string;
}) {
  const id = React.useId();
  const trigger = React.useRef<HTMLButtonElement>(null);
  const menu = React.useRef<HTMLDivElement>(null);
  const [open, setOpen] = React.useState(false);
  const [active, setActive] = React.useState(0);
  const [position, setPosition] = React.useState<CSSProperties>({});
  const search = React.useRef({ text: '', time: 0 });
  const selected = options.find((option) => option.value === value);
  const close = () => menu.current?.hidePopover();
  function show(index = Math.max(0, options.findIndex((option) => option.value === value))) {
    if (!trigger.current || !options.length || disabled) return;
    const rect = trigger.current.getBoundingClientRect();
    const below = window.innerHeight - rect.bottom - 12;
    const above = rect.top - 12;
    const up = below < 180 && above > below;
    const width = Math.min(Math.max(rect.width, 180), window.innerWidth - 24);
    setPosition({ left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)), width,
      top: up ? 'auto' : rect.bottom + 6, bottom: up ? window.innerHeight - rect.top + 6 : 'auto',
      maxHeight: Math.max(80, Math.min(300, up ? above : below)) });
    setActive(index);
    menu.current?.showPopover();
  }
  function choose(index: number) {
    if (options[index]) onChange(options[index].value);
    close();
    trigger.current?.focus();
  }
  function keydown(event: KeyboardEvent<HTMLButtonElement>) {
    const key = event.key;
    if (key === 'Tab') { close(); return; }
    if (key === 'Escape') { if (open) { event.preventDefault(); event.stopPropagation(); close(); } return; }
    if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '].includes(key)) {
      event.preventDefault();
      if (!open) { show(key === 'End' ? options.length - 1 : undefined); return; }
      if (key === 'Enter' || key === ' ') { choose(active); return; }
      setActive((index) => key === 'Home' ? 0 : key === 'End' ? options.length - 1 : (index + (key === 'ArrowUp' ? -1 : 1) + options.length) % options.length);
    } else if (key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const time = Date.now();
      const text = (time - search.current.time < 600 ? search.current.text : '') + key.toLowerCase();
      search.current = { text, time };
      const index = options.findIndex((option) => option.label.toLowerCase().startsWith(text));
      if (index >= 0) { event.preventDefault(); if (open) setActive(index); else show(index); }
    }
  }
  React.useEffect(() => {
    if (open) document.getElementById(`${id}-${active}`)?.scrollIntoView({ block: 'nearest' });
  }, [open, active, id]);
  React.useEffect(() => {
    if (!open) return;
    const hide = (event: Event) => { if (!(event.target instanceof Node) || !menu.current?.contains(event.target)) menu.current?.hidePopover(); };
    window.addEventListener('resize', hide);
    window.addEventListener('scroll', hide, true);
    return () => { window.removeEventListener('resize', hide); window.removeEventListener('scroll', hide, true); };
  }, [open]);
  return <span className={`hum-select ${className}`}>
    {name && <input type="hidden" name={name} value={value} />}
    <button ref={trigger} type="button" className="hum-select-trigger" role="combobox" aria-label={label}
      aria-haspopup="listbox" aria-expanded={open} aria-controls={id} aria-activedescendant={open ? `${id}-${active}` : undefined}
      disabled={disabled || !options.length} data-value={value} onKeyDown={keydown} onClick={() => open ? close() : show()}>
      <span>{selected?.label ?? '请选择'}</span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
    </button>
    <div ref={menu} id={id} popover="auto" className="hum-select-menu" role="listbox" aria-label={label} style={position}
      onToggle={(event) => setOpen(event.newState === 'open')}>
      {options.map((option, index) => <div key={option.value} id={`${id}-${index}`} role="option" aria-selected={option.value === value}
        data-value={option.value} className={`hum-select-option${index === active ? ' is-active' : ''}`}
        onPointerMove={() => setActive(index)} onPointerDown={(event) => event.preventDefault()} onClick={() => choose(index)}>
        <span>{option.label}</span>{option.value === value && <span aria-hidden="true">✓</span>}
      </div>)}
    </div>
  </span>;
}
