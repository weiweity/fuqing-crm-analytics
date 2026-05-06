/**
 * useApi — 基于 openapi-typescript 生成类型的 API 调用 Composable
 *
 * 用法示例：
 *
 * import { useApi } from '@/api/useApi'
 * import type { paths } from '@/api/types'
 *
 * // 方式1：自动类型（推荐）
 * const { data, loading, error } = useApi('/api/v1/metrics/overview', {
 *   query: { start_date: '2026-01-01', end_date: '2026-01-31', metric_type: 'GMV' }
 * })
 *
 * // 方式2：手动指定返回类型
 * const { data } = useApi<'/api/v1/metrics/overview'>('/api/v1/metrics/overview', {
 *   query: { ... }
 * })
 */

import { useQuery, type UseQueryOptions } from '@tanstack/vue-query'
import { computed, type Ref, type ComputedRef } from 'vue'
import client from './index'
import type { operations } from './types'

// openapi-typescript 生成的操作类型映射
export type OperationKey = keyof operations

// 从 operations 提取指定路径+方法的参数和响应类型
export type ExtractOperation<K extends OperationKey> = operations[K]

export type HttpMethod = 'get' | 'post' | 'put' | 'delete' | 'patch'

export interface UseApiOptions<
  TPath extends OperationKey = OperationKey,
  TMethod extends HttpMethod = HttpMethod,
> {
  /** 路径类型推断锚点（phantom，不影响实际行为） */
  readonly _?: TPath
  readonly _m?: TMethod
  query?: Ref<Record<string, unknown>> | ComputedRef<Record<string, unknown>>
  /** 请求体（POST/PUT/PATCH） */
  body?: Ref<Record<string, unknown> | undefined> | ComputedRef<Record<string, unknown> | undefined>
  /** TanStack Query 选项 */
  queryOptions?: Partial<UseQueryOptions>
  /** 立即执行，false 时需手动 refetch */
  immediate?: boolean
}

// 通用的 useApi 实现（方式1：自动类型）
function useApiInternal(
  path: string,
  options?: {
    query?: Ref<Record<string, unknown>> | ComputedRef<Record<string, unknown>>
    method?: HttpMethod
    body?: Ref<Record<string, unknown> | undefined> | ComputedRef<Record<string, unknown> | undefined>
    queryOptions?: Partial<UseQueryOptions>
    immediate?: boolean
  }
) {
  const {
    query = undefined,
    method = 'get',
    body = undefined,
    queryOptions = {},
    immediate = true,
  } = options ?? {}

  const queryKey = computed(() => [
    path,
    query?.value,
    method,
    body?.value,
  ])

  const queryFn = async () => {
    const config: Record<string, unknown> = {}
    if (query?.value) config.params = query.value
    if (body?.value) config.data = body.value

    switch (method) {
      case 'get':
        return client.get(path, config)
      case 'post':
        return client.post(path, config.data, { params: config.params })
      case 'put':
        return client.put(path, config.data, { params: config.params })
      case 'delete':
        return client.delete(path, { params: config.params })
      case 'patch':
        return client.patch(path, config.data, { params: config.params })
    }
  }

  return useQuery({
    queryKey,
    queryFn,
    enabled: immediate,
    retry: 1,
    retryDelay: 1000,
    refetchOnWindowFocus: false,
    ...queryOptions,
  })
}

/**
 * GET 请求（自动类型）
 * @example
 * const { data } = useApi('/api/v1/metrics/overview', {
 *   query: computed(() => ({ start_date: '2026-01-01', end_date: '2026-01-31' }))
 * })
 */
export function useApi<TPath extends OperationKey>(
  path: TPath,
  options?: UseApiOptions<TPath>
) {
  return useApiInternal(
    path as string,
    {
      query: options?.query as Ref<Record<string, unknown>> | ComputedRef<Record<string, unknown>> | undefined,
      method: 'get',
      body: options?.body as Ref<Record<string, unknown> | undefined> | ComputedRef<Record<string, unknown> | undefined>,
      queryOptions: options?.queryOptions,
      immediate: options?.immediate,
    }
  )
}

/**
 * POST 请求
 */
export function useApiPost<TPath extends OperationKey>(
  path: TPath,
  options?: UseApiOptions<TPath>
) {
  return useApiInternal(
    path as string,
    {
      query: options?.query as Ref<Record<string, unknown>> | ComputedRef<Record<string, unknown>> | undefined,
      method: 'post',
      body: options?.body as Ref<Record<string, unknown> | undefined> | ComputedRef<Record<string, unknown> | undefined>,
      queryOptions: options?.queryOptions,
      immediate: options?.immediate,
    }
  )
}

// Re-export 所有生成类型，方便外部引用
export * from './types'
