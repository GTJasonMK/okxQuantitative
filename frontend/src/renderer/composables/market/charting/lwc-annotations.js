// K 线图标注系统 — Lightweight Charts Primitives 实现
// 支持趋势线、水平线、矩形框、测距尺四种标注工具
// 通过 series.attachPrimitive() 接入 LWC 的插件体系

/**
 * 基础标注 Primitive 抽象类
 * 所有标注类型继承此类，实现 paneViews() 和 draw() 方法
 */
class BaseAnnotationPrimitive {
  constructor(options = {}) {
    this.id = options.id || `ann_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.type = options.type || 'unknown';
    this.color = options.color || '#F7931A';
    this.lineWidth = options.lineWidth || 1.5;
    this.selected = false;
    this.source = options.source || 'user';
    this._series = null;
    this._requestUpdate = null;
  }

  attached({ series, requestUpdate }) {
    this._series = series;
    this._requestUpdate = requestUpdate;
  }

  detached() {
    this._series = null;
    this._requestUpdate = null;
  }

  requestUpdate() {
    this._requestUpdate?.();
  }

  setSelected(selected) {
    this.selected = selected;
    this.requestUpdate();
  }

  updateAllViews() {}
  priceAxisViews() { return []; }
  timeAxisViews() { return []; }
  paneViews() { return [this]; }

  // 坐标转换辅助：时间值 → 像素 X
  _timeToX(timeValue, scope) {
    const ts = scope.chart.timeScale();
    return ts.timeToCoordinate(timeValue) ?? null;
  }

  // 坐标转换辅助：价格值 → 像素 Y
  _priceToY(priceValue, scope) {
    const s = scope.series;
    return s.priceToCoordinate(priceValue) ?? null;
  }

  // 子类必须实现
  renderer() { return null; }

  toJSON() {
    return { id: this.id, type: this.type, color: this.color, source: this.source };
  }
}

// ===== 水平线 =====
export class HorizontalLinePrimitive extends BaseAnnotationPrimitive {
  constructor(options = {}) {
    super({ ...options, type: 'horizontal' });
    this.price = options.price || 0;
    this.style = options.style || 'solid'; // solid, dashed
    this.label = options.label || '';
  }

  renderer() {
    return {
      draw: (target) => {
        const ctx = target.context;
        const series = this._series;
        if (!series) return;

        const y = series.priceToCoordinate(this.price);
        if (y === null || y === undefined) return;

        const { width } = target.mediaSize;
        ctx.save();
        ctx.strokeStyle = this.color;
        ctx.lineWidth = this.selected ? this.lineWidth + 1 : this.lineWidth;
        if (this.style === 'dashed') ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();

        // 价格标签
        if (this.label || this.price) {
          const text = this.label || this.price.toFixed(2);
          ctx.font = '10px Inter, sans-serif';
          const textWidth = ctx.measureText(text).width;
          ctx.fillStyle = this.color;
          ctx.globalAlpha = 0.85;
          ctx.fillRect(width - textWidth - 12, y - 9, textWidth + 8, 18);
          ctx.globalAlpha = 1;
          ctx.fillStyle = '#fff';
          ctx.fillText(text, width - textWidth - 8, y + 4);
        }

        ctx.restore();
      },
    };
  }

  toJSON() {
    return { ...super.toJSON(), price: this.price, label: this.label, style: this.style };
  }
}

// ===== 趋势线 =====
export class TrendLinePrimitive extends BaseAnnotationPrimitive {
  constructor(options = {}) {
    super({ ...options, type: 'trendline' });
    this.p1 = options.p1 || { time: 0, price: 0 }; // { time (unix seconds), price }
    this.p2 = options.p2 || { time: 0, price: 0 };
  }

  renderer() {
    return {
      draw: (target) => {
        const ctx = target.context;
        const series = this._series;
        if (!series) return;

        const chart = series.chart?.();
        if (!chart) return;

        const x1 = chart.timeScale().timeToCoordinate(this.p1.time);
        const y1 = series.priceToCoordinate(this.p1.price);
        const x2 = chart.timeScale().timeToCoordinate(this.p2.time);
        const y2 = series.priceToCoordinate(this.p2.price);

        if (x1 == null || y1 == null || x2 == null || y2 == null) return;

        ctx.save();
        ctx.strokeStyle = this.color;
        ctx.lineWidth = this.selected ? this.lineWidth + 1 : this.lineWidth;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        // 端点圆圈
        if (this.selected) {
          ctx.fillStyle = this.color;
          [{ x: x1, y: y1 }, { x: x2, y: y2 }].forEach(({ x, y }) => {
            ctx.beginPath();
            ctx.arc(x, y, 4, 0, Math.PI * 2);
            ctx.fill();
          });
        }

        ctx.restore();
      },
    };
  }

  toJSON() {
    return { ...super.toJSON(), p1: this.p1, p2: this.p2 };
  }
}

// ===== 矩形框 =====
export class RectanglePrimitive extends BaseAnnotationPrimitive {
  constructor(options = {}) {
    super({ ...options, type: 'rectangle' });
    this.p1 = options.p1 || { time: 0, price: 0 };
    this.p2 = options.p2 || { time: 0, price: 0 };
    this.fillColor = options.fillColor || 'rgba(247, 147, 26, 0.08)';
  }

  renderer() {
    return {
      draw: (target) => {
        const ctx = target.context;
        const series = this._series;
        if (!series) return;

        const chart = series.chart?.();
        if (!chart) return;

        const x1 = chart.timeScale().timeToCoordinate(this.p1.time);
        const y1 = series.priceToCoordinate(this.p1.price);
        const x2 = chart.timeScale().timeToCoordinate(this.p2.time);
        const y2 = series.priceToCoordinate(this.p2.price);

        if (x1 == null || y1 == null || x2 == null || y2 == null) return;

        const left = Math.min(x1, x2);
        const top = Math.min(y1, y2);
        const w = Math.abs(x2 - x1);
        const h = Math.abs(y2 - y1);

        ctx.save();
        // 填充
        ctx.fillStyle = this.fillColor;
        ctx.fillRect(left, top, w, h);
        // 边框
        ctx.strokeStyle = this.color;
        ctx.lineWidth = this.selected ? this.lineWidth + 0.5 : this.lineWidth;
        ctx.strokeRect(left, top, w, h);

        // 选中时显示角点
        if (this.selected) {
          ctx.fillStyle = this.color;
          [{ x: x1, y: y1 }, { x: x2, y: y2 }, { x: x1, y: y2 }, { x: x2, y: y1 }].forEach(({ x, y }) => {
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fill();
          });
        }

        ctx.restore();
      },
    };
  }

  toJSON() {
    return { ...super.toJSON(), p1: this.p1, p2: this.p2, fillColor: this.fillColor };
  }
}

// ===== 测距尺 =====
export class RulerPrimitive extends BaseAnnotationPrimitive {
  constructor(options = {}) {
    super({ ...options, type: 'ruler' });
    this.p1 = options.p1 || { time: 0, price: 0 };
    this.p2 = options.p2 || { time: 0, price: 0 };
  }

  renderer() {
    return {
      draw: (target) => {
        const ctx = target.context;
        const series = this._series;
        if (!series) return;

        const chart = series.chart?.();
        if (!chart) return;

        const x1 = chart.timeScale().timeToCoordinate(this.p1.time);
        const y1 = series.priceToCoordinate(this.p1.price);
        const x2 = chart.timeScale().timeToCoordinate(this.p2.time);
        const y2 = series.priceToCoordinate(this.p2.price);

        if (x1 == null || y1 == null || x2 == null || y2 == null) return;

        ctx.save();
        // 虚线连接
        ctx.strokeStyle = this.color;
        ctx.lineWidth = this.lineWidth;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        // 端点
        ctx.fillStyle = this.color;
        ctx.setLineDash([]);
        [{ x: x1, y: y1 }, { x: x2, y: y2 }].forEach(({ x, y }) => {
          ctx.beginPath();
          ctx.arc(x, y, 3, 0, Math.PI * 2);
          ctx.fill();
        });

        // 测距标签
        const priceDelta = this.p2.price - this.p1.price;
        const pctDelta = this.p1.price !== 0 ? (priceDelta / this.p1.price * 100) : 0;
        const sign = priceDelta >= 0 ? '+' : '';
        const label = `${sign}${priceDelta.toFixed(2)} (${sign}${pctDelta.toFixed(2)}%)`;

        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;
        ctx.font = '11px "JetBrains Mono", monospace';
        const textWidth = ctx.measureText(label).width;
        const pad = 6;
        const bgColor = priceDelta >= 0 ? 'rgba(34, 197, 94, 0.9)' : 'rgba(239, 68, 68, 0.9)';
        ctx.fillStyle = bgColor;
        ctx.fillRect(midX - textWidth / 2 - pad, midY - 10, textWidth + pad * 2, 20);
        ctx.fillStyle = '#fff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, midX, midY);

        ctx.restore();
      },
    };
  }

  toJSON() {
    return { ...super.toJSON(), p1: this.p1, p2: this.p2 };
  }
}

// ===== 标注管理器 =====

/**
 * 管理所有标注 primitives 的生命周期
 * 与 lwc-kline.js 的 createKlineChartManager 配合使用
 */
export class AnnotationManager {
  constructor() {
    this._primitives = new Map(); // id → primitive
    this._series = null;
    this._selectedId = null;
  }

  /**
   * 绑定到 LWC candlestick series
   */
  bind(candleSeries) {
    this._series = candleSeries;
    // 重新 attach 已有的 primitives
    for (const primitive of this._primitives.values()) {
      candleSeries.attachPrimitive(primitive);
    }
  }

  /**
   * 解绑并移除所有 primitives
   */
  unbind() {
    if (this._series) {
      for (const primitive of this._primitives.values()) {
        try { this._series.detachPrimitive(primitive); } catch (_) {}
      }
    }
    this._series = null;
  }

  /**
   * 添加标注
   */
  add(primitive) {
    if (!primitive?.id) return;
    this._primitives.set(primitive.id, primitive);
    if (this._series) {
      this._series.attachPrimitive(primitive);
    }
  }

  /**
   * 移除标注
   */
  remove(id) {
    const primitive = this._primitives.get(id);
    if (!primitive) return false;
    if (this._series) {
      try { this._series.detachPrimitive(primitive); } catch (_) {}
    }
    this._primitives.delete(id);
    if (this._selectedId === id) this._selectedId = null;
    return true;
  }

  /**
   * 移除最后一个标注
   */
  removeLast() {
    const ids = [...this._primitives.keys()];
    if (ids.length === 0) return false;
    return this.remove(ids[ids.length - 1]);
  }

  /**
   * 清空所有标注
   */
  clear() {
    for (const id of [...this._primitives.keys()]) {
      this.remove(id);
    }
    this._selectedId = null;
  }

  /**
   * 按 source 清空
   */
  clearBySource(sources) {
    const sourceSet = new Set(Array.isArray(sources) ? sources : [sources]);
    for (const [id, primitive] of this._primitives.entries()) {
      if (sourceSet.has(primitive.source)) {
        this.remove(id);
      }
    }
  }

  /**
   * 选中/取消选中
   */
  select(id) {
    if (this._selectedId && this._primitives.has(this._selectedId)) {
      this._primitives.get(this._selectedId).setSelected(false);
    }
    this._selectedId = id;
    if (id && this._primitives.has(id)) {
      this._primitives.get(id).setSelected(true);
    }
  }

  clearSelection() {
    this.select(null);
  }

  getSelected() {
    return this._selectedId ? this._primitives.get(this._selectedId) || null : null;
  }

  get count() { return this._primitives.size; }

  getCountBySource(sources) {
    const sourceSet = new Set(Array.isArray(sources) ? sources : [sources]);
    let count = 0;
    for (const primitive of this._primitives.values()) {
      if (sourceSet.has(primitive.source)) count++;
    }
    return count;
  }

  getAll() { return [...this._primitives.values()]; }

  /**
   * 序列化（用于持久化）
   */
  exportAll() {
    return this.getAll().map(p => p.toJSON());
  }

  /**
   * 反序列化
   */
  importAll(items) {
    this.clear();
    for (const item of items) {
      let primitive = null;
      switch (item.type) {
        case 'horizontal':
          primitive = new HorizontalLinePrimitive(item);
          break;
        case 'trendline':
          primitive = new TrendLinePrimitive(item);
          break;
        case 'rectangle':
          primitive = new RectanglePrimitive(item);
          break;
        case 'ruler':
          primitive = new RulerPrimitive(item);
          break;
      }
      if (primitive) {
        primitive.id = item.id || primitive.id;
        this.add(primitive);
      }
    }
  }
}
