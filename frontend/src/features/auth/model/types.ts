export type LoginPayload = {
  username_or_email: string;
  password: string;
  tenant_code?: string;
  captcha?: string;
  remember_me?: boolean;
};

export type AuthUser = {
  id?: string;
  username: string;
  full_name?: string;
  roles: string[];
  permissions: string[];
  mfa_required: boolean;
};

export type LoginResponse = {
  tokens?: { access_token: string; refresh_token: string } | null;
  user: AuthUser;
  requires_mfa: boolean;
  challenge_id?: string | null;
};

export type MfaVerifyResponse = {
  verified: boolean;
  tokens?: { access_token: string };
};
