// 异步请求工具：节流、防抖、可中止请求、最新请求保护

/**
 * 节流函数 — 限制函数执行频率
 * @param {Function} fn 目标函数
 * @param {number} delay 最小间隔（毫秒）
 * @returns {Function} 节流后的函数
 */
export const throttle = (fn, delay) => {
  let lastCall = 0;
  return (...args) => {
    const now = Date.now();
    if (now - lastCall >= delay) {
      lastCall = now;
      fn(...args);
    }
  };
};

/**
 * 防抖函数 — 延迟执行，期间重复调用重新计时
 * @param {Function} fn 目标函数
 * @param {number} delay 延迟毫秒
 * @returns {{ run: Function, cancel: Function }} 带 cancel 的防抖对象
 */
export const debounce = (fn, delay) => {
  let timer = null;
  const run = (...args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn(...args);
    }, delay);
  };
  const cancel = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  };
  return { run, cancel };
};

/**
 * 创建一个"最新请求胜出"的请求包装器。
 * 快速切换参数时，旧请求的响应会被丢弃，只有最后一次调用的结果被采纳。
 * 同时支持通过 AbortController 取消旧的 in-flight 请求。
 *
 * @returns {{ run: (asyncFn: (signal: AbortSignal) => Promise<T>) => Promise<T|undefined>, abort: () => void }}
 */
export const createLatestOnly = () => {
  let currentVersion = 0;
  let currentController = null;

  const abort = () => {
    if (currentController) {
      currentController.abort();
      currentController = null;
    }
  };

  /**
   * @template T
   * @param {(signal: AbortSignal) => Promise<T>} asyncFn
   * @returns {Promise<T|undefined>}
   */
  const run = async (asyncFn) => {
    abort();
    const version = ++currentVersion;
    const controller = new AbortController();
    currentController = controller;

    try {
      const result = await asyncFn(controller.signal);
      // 如果在等待期间又有新调用，丢弃本次结果
      if (currentVersion !== version) {
        return undefined;
      }
      return result;
    } catch (error) {
      // AbortError 是正常的取消行为，静默丢弃
      if (error?.name === 'AbortError') {
        return undefined;
      }
      // 过期请求的错误也丢弃
      if (currentVersion !== version) {
        return undefined;
      }
      throw error;
    } finally {
      if (currentController === controller) {
        currentController = null;
      }
    }
  };

  return { run, abort };
};

/**
 * 二分查找 — 在按时间戳升序排列的 K 线数组中定位目标时间戳所属的 K 线索引
 * @param {Array<{timestamp: number}>} candles K 线数组
 * @param {number} targetTs 目标时间戳
 * @param {number} duration K 线周期（毫秒）
 * @returns {number} 索引，找不到返回 -1
 */
export const binarySearchCandleIndex = (candles, targetTs, duration) => {
  let left = 0;
  let right = candles.length - 1;
  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const candleStart = candles[mid].timestamp;
    const candleEnd = candleStart + duration;
    if (targetTs >= candleStart && targetTs < candleEnd) {
      return mid;
    } else if (targetTs < candleStart) {
      right = mid - 1;
    } else {
      left = mid + 1;
    }
  }
  return -1;
};
