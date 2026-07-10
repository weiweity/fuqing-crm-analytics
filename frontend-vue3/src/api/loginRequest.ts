/**
 * L4.85 申请+同意 模式 API 客户端 (跟后端 backend/routers/login_request.py 4 endpoint 1:1 stable 配套)
 *
 * 业务模式 (跟 L4.42 立项实证 SOP 1:1 stable 配套, user 7/10 拍板):
 * - A 已登录 (active)
 * - B 尝试登录 admin → 看到 "账号正在被使用" 提示
 * - B 提交申请 (loginRequest) → 收到 request_id
 * - A 收到申请 (getPendingLoginRequests polling 5s) → 看到 "B 申请登录"
 * - A 点 "同意" (approveLoginRequest) → A 登出, B 登录成功
 * - A 点 "拒绝" (rejectLoginRequest) → A 不受影响, B 看到 "申请被拒绝"
 * - 5 分钟超时 → 自动 expired
 *
 * 跟 L4.84 自动踢 (admin 二次登录踢第一次) 互补不冲突 (跟 L4.42 + L4.85 1:1 stable 永久规则链配套)
 */
import client from './index'

export interface LoginRequestResponse {
  request_id: string
  status: 'pending' | 'approved' | 'rejected' | 'expired'
  message: string
}

export interface PendingLoginRequest {
  request_id: string
  requester_ip: string
  created_at: number
  status: 'pending' | 'approved' | 'rejected' | 'expired'
  estimated_wait_seconds: number
}

export interface PendingLoginRequestsResponse {
  pending: PendingLoginRequest[]
}

export interface ApproveLoginRequestResponse {
  success: boolean
  new_token: string
  username: string
}

export interface RejectLoginRequestResponse {
  success: boolean
}

export interface LoginRequestStatusResponse {
  request_id: string
  status: 'pending' | 'approved' | 'rejected' | 'expired'
  new_token?: string
  username?: string
}

/**
 * L4.85 治本: B 申请登录 admin (admin 当前 active)
 *
 * 跟 L4.42 立项实证 SOP 1:1 stable 配套, 跟后端 POST /api/v1/auth/login-request 1:1 stable 配套.
 * 返回 200 + {request_id, status: "pending", message: "账号正在被使用, 已发送申请给当前用户"}.
 * 返回 409 (账号当前未激活, 请直接走 /api/v1/auth/login).
 * 返回 401 (账号或密码错误).
 */
export async function loginRequest(
  username: string,
  password: string
): Promise<LoginRequestResponse> {
  const res = await client.post<LoginRequestResponse>('/v1/auth/login-request', {
    username,
    password,
  }) as unknown as LoginRequestResponse
  return res
}

/**
 * L4.85 治本: A 查待处理申请 (A 必须是 active 用户)
 *
 * 跟后端 GET /api/v1/auth/login-requests/pending 1:1 stable 配套.
 * A 端 polling 5s 调一次, 看到 B 申请时显示 "同意/拒绝" 弹窗.
 */
export async function getPendingLoginRequests(): Promise<PendingLoginRequestsResponse> {
  const res = await client.get<PendingLoginRequestsResponse>(
    '/v1/auth/login-requests/pending'
  ) as unknown as PendingLoginRequestsResponse
  return res
}

/**
 * L4.85 治本: A 同意 B 的申请 → A 登出, B 登录 (跟 L4.84 _evict_previous_sessions_for_user 1:1 stable 复用)
 *
 * 跟后端 POST /api/v1/auth/login-request/{request_id}/approve 1:1 stable 配套.
 * 返回 {success: true, new_token, username}, B 用 new_token 替换本地 token.
 */
export async function approveLoginRequest(
  requestId: string
): Promise<ApproveLoginRequestResponse> {
  const res = await client.post<ApproveLoginRequestResponse>(
    `/v1/auth/login-request/${requestId}/approve`
  ) as unknown as ApproveLoginRequestResponse
  return res
}

/**
 * L4.85 治本: A 拒绝 B 的申请 (A 不受影响)
 *
 * 跟后端 POST /api/v1/auth/login-request/{request_id}/reject 1:1 stable 配套.
 */
export async function rejectLoginRequest(
  requestId: string
): Promise<RejectLoginRequestResponse> {
  const res = await client.post<RejectLoginRequestResponse>(
    `/v1/auth/login-request/${requestId}/reject`
  ) as unknown as RejectLoginRequestResponse
  return res
}

/**
 * L4.85.1 治本: B 端 polling 检测自己申请状态 (跟 NavBar.vue 强制弹窗 + 强制退出 1:1 stable 永久规则化沿用)
 *
 * 跟后端 GET /api/v1/auth/login-request/{request_id}/status 1:1 stable 配套.
 * - status="pending" → B 端继续等待
 * - status="approved" → 返回 new_token, B 端 receive 后写入 sessionStorage + router.push
 * - status="rejected" / "expired" → B 端显示提示
 */
export async function getLoginRequestStatus(
  requestId: string
): Promise<LoginRequestStatusResponse> {
  const res = await client.get<LoginRequestStatusResponse>(
    `/v1/auth/login-request/${requestId}/status`
  ) as unknown as LoginRequestStatusResponse
  return res
}
