import type { Analytics, Distribution } from '../services/preview';
import type { ChartOption } from './EChart';
import { compact } from './common';

const scaled = (value: number | null) => value == null ? null : value / 1_000_000;
const formatScaled = (value: unknown) => typeof value === 'number' ? new Intl.NumberFormat('en-US', { maximumFractionDigits: 6 }).format(value) : '—';
const tokenTooltip = { valueFormatter: (value: unknown) => `${formatScaled(value)} M Token` };

export const colors = ['#6750a4', '#8268b9', '#9980d0', '#b3a0e2', '#cbbbf4', '#ddd2fa', '#a896d0', '#e7dff6', '#85749f', '#a49caf', '#d0c7dc', '#f0e9fa'];
const axis = { axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#77717e', fontSize: 11 }, splitLine: { lineStyle: { color: '#e4dfeb' } } };
export function trendOption(data: Analytics, mode: 'overview' | 'usage' | 'mcp'): ChartOption {
  const main = data.trend;
  return { color: ['#cbbbf4', '#9980d0', '#6750a4', '#b1cf19'], tooltip: { trigger: 'axis', renderMode: 'richText', confine: true },
    legend: { bottom: 0, textStyle: { color: '#77717e', fontSize: 11 } }, grid: { top: 26, left: 60, right: 56, bottom: 64 },
    xAxis: { ...axis, type: 'category', data: main.map((item) => item.day.length === 10 ? item.day.slice(5) : item.day), boundaryGap: mode === 'usage' },
    yAxis: [{ ...axis, type: 'value', name: mode === 'mcp' ? '调用次数' : 'M Token', axisLabel: { formatter: mode === 'mcp' ? compact : formatScaled, color: '#77717e' } }, ...(mode === 'mcp' ? [] : [{ ...axis, type: 'value' as const, name: '活跃人数', minInterval: 1, splitLine: { show: false } }])],
    series: mode === 'mcp' ? [{ type: 'line', name: 'MCP 调用', smooth: true, data: main.map((item) => item.calls), itemStyle: { color: '#8268b9' }, areaStyle: { opacity: 0.16 }, showSymbol: false }]
      : mode === 'overview' ? [{ type: 'line', name: '用量', smooth: true, data: main.map((item) => scaled(item.total_tokens)), tooltip: tokenTooltip, itemStyle: { color: '#8b87e8' } }, { type: 'line', name: '活跃人数', yAxisIndex: 1, smooth: true, data: main.map((item) => item.active), itemStyle: { color: '#b1cf19' } }]
        : [...(['cached', 'input', 'output'] as const).map((key, index) => ({ type: 'bar' as const, name: ['输入（命中缓存）', '输入（未命中缓存）', '输出'][index], stack: 'tokens', data: main.map((item) => scaled(item[key])), tooltip: tokenTooltip, barMaxWidth: 44 })), { type: 'line', name: '活跃人数', yAxisIndex: 1, smooth: true, data: main.map((item) => item.active) }] };
}

export function pieOption(rows: Distribution[], metric: 'tokens' | 'cost'): ChartOption {
  const sorted = rows.filter((item) => item[metric] != null).sort((first, second) => (second[metric] ?? 0) - (first[metric] ?? 0));
  const top = sorted.slice(0, 9);
  const factor = metric === 'tokens' ? 1_000_000 : 1;
  const data = top.map((item) => ({ name: item.name, value: (item[metric] ?? 0) / factor }));
  if (sorted.length > 9) data.push({ name: '其他', value: sorted.slice(9).reduce((sum, item) => sum + (item[metric] ?? 0), 0) / factor });
  return { color: colors, tooltip: { trigger: 'item', renderMode: 'richText', confine: true, formatter: metric === 'tokens' ? (params: unknown) => {
    if (!params || typeof params !== 'object') return '';
    const item = params as { name?: string; value?: number; percent?: number };
    return `${item.name ?? ''}\n${formatScaled(item.value)} M Token (${formatScaled(item.percent)}%)`;
  } : '{b}\n${c} USD ({d}%)' }, legend: { type: 'scroll', bottom: 0, textStyle: { fontSize: 10, color: '#77717e' } },
    series: [{ type: 'pie', radius: '58%', center: ['50%', '46%'], avoidLabelOverlap: true, label: { fontSize: 11, color: '#625f68', formatter: '{b}', width: 85, overflow: 'truncate' }, labelLine: { lineStyle: { color: '#c9c3cf' } }, data }] };
}

export function rankOption(rows: { name: string; value: number | null }[], unit: 'tokens' | 'calls' | 'cost' = 'tokens'): ChartOption {
  const mcp = unit === 'calls';
  return { color: ['#9980d0'], tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, renderMode: 'richText', confine: true },
    grid: { left: 100, right: 65, top: 20, bottom: 35 }, xAxis: { ...axis, type: 'value', name: unit === 'tokens' ? 'M Token' : unit === 'cost' ? 'USD' : '次', axisLabel: { formatter: unit === 'tokens' ? formatScaled : compact, color: '#77717e' } },
    yAxis: { ...axis, type: 'category', inverse: true, data: rows.map((item) => item.name), axisLabel: { color: '#625f68', width: 80, overflow: 'truncate' } },
    dataZoom: mcp && rows.length > 10 ? [{ type: 'inside', yAxisIndex: 0, startValue: 0, endValue: 9, filterMode: 'filter' }, { type: 'slider', yAxisIndex: 0, right: 0, width: 9, startValue: 0, endValue: 9, showDetail: false }] : [],
    series: [{ type: 'bar', data: rows.map((item) => unit === 'tokens' ? scaled(item.value) : item.value), tooltip: unit === 'tokens' ? tokenTooltip : {}, barMaxWidth: 18, showBackground: true, backgroundStyle: { color: '#f2ecf8' }, itemStyle: { borderRadius: [0, 4, 4, 0] }, label: { show: true, position: 'right', color: '#625f68', fontSize: 10, formatter: (params: unknown) => params && typeof params === 'object' && 'value' in params ? formatScaled(params.value) : '—' } }] };
}

export function departmentOption(rows: Distribution[], metric: 'tokens' | 'cost'): ChartOption {
  if (metric === 'cost') return { ...rankOption(rows.map((item) => ({ name: item.name, value: item.cost })), 'cost'), color: ['#6750a4'] };
  return { color: ['#cbbbf4', '#9980d0', '#6750a4'], tooltip: { trigger: 'axis', renderMode: 'richText', confine: true }, legend: { bottom: 0, textStyle: { fontSize: 10 } },
    grid: { left: 55, right: 25, top: 25, bottom: 68 }, xAxis: { ...axis, type: 'category', data: rows.map((item) => item.name) }, yAxis: { ...axis, type: 'value', name: 'M Token', axisLabel: { formatter: formatScaled, color: '#77717e' } },
    series: (['cached', 'input', 'output'] as const).map((field, index) => ({ type: 'bar', stack: 'tokens', name: ['输入（命中缓存）', '输入（未命中缓存）', '输出'][index], data: rows.map((item) => scaled(item[field])), tooltip: tokenTooltip, barMaxWidth: 50 })) };
}
