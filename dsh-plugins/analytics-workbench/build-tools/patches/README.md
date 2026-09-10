# 固定 React 18 的声明兼容

固定 DSH 使用 React 18.3.1 / @types/react 18.3.31。AntD 5.29.3 的两项依赖声明不通过 `skipLibCheck=false`；本目录仅修补发布包的 `.d.ts`，由 pnpm-workspace.yaml 绑定准确版本、锁文件绑定补丁摘要。

- `antd@5.29.3.patch`：useForceUpdate 实现是无 action 的 useReducer，返回 `[number, DispatchWithoutAction]`。发布声明引用 React 19 的 ActionDispatch；改用 React 18 已有且对应实际实现的类型，es/lib 保持一致。
- `rc-picker@4.11.3.patch`：SinglePickerPanelProps 原本显式接受 nullable defaultValue，但继承的 SharedTimeProps 含同名非 nullable 属性而无法扩展。只在该派生接口排除继承的同名属性，保留既有自身声明；不改运行时代码或其余属性。

上游修正相应声明，且候选在固定工具链的完整类型检查、组件回归和干净重建通过后，再移除对应补丁。不要跳过声明检查、加入 any 模块或升级 DSH 的 React 来掩盖问题。

`js-yaml@4.3.1 → 4.3.2` 是原 openapi-typescript 依赖链的独立安全修复，依据 [GHSA-2883-xcg3-v3hh](https://github.com/advisories/GHSA-2883-xcg3-v3hh)。override 仅针对 4.3.1；依赖自身已解析至修复版本后可移除。
