<script setup lang="ts">
/**
 * BaseStyleButton — Learn More 风格按钮（Sprint 172 用户拍板新版）
 *
 * 设计来源: Codepen Learn More 经典「圆拉长填充」动效, 文字 hover 时从右滑入中心.
 * Sprint 172 改造为:
 *   1. emoji 全部去掉 (用户拍板 AI 化太严重)
 *   2. 大小统一 (跟 <h3 class="text-sm"> 同层 13px / 28px 高)
 *   3. 颜色硬约束 #282936 (深蓝黑, 不沿用项目深蓝主题)
 *   4. 箭头方向可切换 (← 收起 / 显示 →)
 *
 * 设计原则:
 *   - 单文件 scoped CSS, 不污染全局
 *   - 单一尺寸 (不再有 sm 变体), 用户拍板"最后所有的这个设计都统一大小"
 *   - 中文 700 字重 (text-transform uppercase noop for CJK, 这里依赖 font-weight 700)
 */

type Mode = 'expand' | 'collapse' | 'neutral'

const props = withDefaults(
  defineProps<{
    /** 箭头方向: expand=显示→ collapse=收起← neutral=纯文字无方向 */
    mode?: Mode
    /** 自定义 class 用于外部覆盖 */
    customClass?: string
  }>(),
  { mode: 'neutral' },
)

const ARROW: Record<Mode, string> = {
  expand: '→',
  collapse: '←',
  neutral: '',
}
</script>

<template>
  <button
    :class="[
      'base-style-btn',
      'learn-more',
      `base-style-btn--${props.mode}`,
      props.customClass || '',
    ]"
  >
    <span class="circle">
      <span class="icon arrow" />
    </span>
    <span class="button-text">
      <slot />
      <span v-if="ARROW[props.mode]" class="ml-1">{{ ARROW[props.mode] }}</span>
    </span>
  </button>
</template>

<style scoped>
.base-style-btn.learn-more {
  /* 尺寸变量 — 跟 <h3 class="text-sm"> 文案基线对齐, 跨 Sprint 172 全部统一 */
  --btn-w: 130px;
  --btn-h: 28px;
  --btn-fs: 13px;
  --btn-bg: #282936;
  --btn-fg: #fff;

  position: relative;
  display: inline-flex;          /* 中文一行排版更稳 */
  align-items: center;
  width: var(--btn-w);
  height: var(--btn-h);
  cursor: pointer;
  outline: none;
  border: 0;
  vertical-align: middle;
  text-decoration: none;
  background: transparent;
  padding: 0;
  font-size: var(--btn-fs);
  font-family: inherit;
  color: inherit;
  overflow: hidden;              /* 防止圆 ::before 渲染越界 */
  white-space: nowrap;
}

.base-style-btn.learn-more .circle {
  transition: all 0.45s cubic-bezier(0.65, 0, 0.076, 1);
  position: absolute;
  top: 0;
  left: 0;
  display: block;
  margin: 0;
  width: 1.625rem;
  height: 1.625rem;
  background: var(--btn-bg);
  border-radius: 1.625rem;
}

.base-style-btn.learn-more .circle .icon.arrow {
  transition: all 0.45s cubic-bezier(0.65, 0, 0.076, 1);
  position: absolute;
  top: 0;
  bottom: 0;
  margin: auto;
  left: 0.4rem;
  width: 0.85rem;
  height: 0.125rem;
  background: #fff;
}

/* 箭头头部 — 三角用 border 拼 */
.base-style-btn.learn-more .circle .icon.arrow::before {
  position: absolute;
  content: '';
  top: -0.25rem;
  right: 0.0625rem;
  width: 0.55rem;
  height: 0.55rem;
  border-top: 0.125rem solid #fff;
  border-right: 0.125rem solid #fff;
  transform: rotate(45deg);
  transition: all 0.45s cubic-bezier(0.65, 0, 0.076, 1);
}

/* 模式联动: collapse 箭头朝左 (←) */
.base-style-btn--collapse .circle .icon.arrow::before {
  top: -0.25rem;
  right: auto;
  left: 0.0625rem;
  transform: rotate(-135deg);
}

.base-style-btn--collapse .circle .icon.arrow {
  left: 0.4rem;
}

.base-style-btn.learn-more .button-text {
  transition: all 0.45s cubic-bezier(0.65, 0, 0.076, 1);
  position: absolute;
  top: 0;
  left: 1.85rem;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  margin: 0;
  color: var(--btn-bg);
  font-weight: 700;
  line-height: 1.5;
  text-align: center;
  /* text-transform: uppercase 在源设计稿有, 但对 CJK 无效 (noop),
     这里保留显式注释避免后人误删; 中文字符在字体上自然呈现 700 字重 */
}

/* Hover — 圆拉长 */
.base-style-btn.learn-more:hover .circle {
  width: 100%;
}

/* Hover — 箭头平移出圆外, 用户视觉看到「圆盖住整按钮」 */
.base-style-btn.learn-more:hover .circle .icon.arrow {
  background: #fff;
  transform: translate(0.45rem, 0);
}

.base-style-btn--collapse.learn-more:hover .circle .icon.arrow {
  transform: translate(0.45rem, 0);
}

/* Hover — 文字变白 (被圆覆盖了所以藏在白色底里) */
.base-style-btn.learn-more:hover .button-text {
  color: #fff;
}

.base-style-btn.learn-more:focus-visible {
  outline: 2px solid var(--btn-bg);
  outline-offset: 2px;
}
</style>
