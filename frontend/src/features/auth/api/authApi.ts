import { httpClient } from '../../../shared/api/httpClient';
import type { LoginPayload, LoginResponse, MfaVerifyResponse } from '../model/types';

export const authApi = {
  login(payload: LoginPayload) {
    return httpClient<LoginResponse>('/auth/login', { method: 'POST', body: JSON.stringify(payload) });
  },
  verifyMfa(payload: { challenge_id?: string; otp_code?: string; authenticator_code?: string; recovery_code?: string }) {
    return httpClient<MfaVerifyResponse>('/auth/mfa/verify', { method: 'POST', body: JSON.stringify(payload) });
  }
};
