export type Role = "consumer" | "provider" | "admin";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  headline: string;
  bio: string;
  avatar_color: string;
  is_active: boolean;
  created_at: string;
}

export interface UserPublic {
  id: number;
  full_name: string;
  role: Role;
  headline: string;
  avatar_color: string;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  icon: string;
  description: string;
}

export interface Service {
  id: number;
  title: string;
  slug: string;
  description: string;
  price_cents: number;
  delivery_days: number;
  tags: string;
  status: "draft" | "active" | "paused";
  rating_avg: number;
  rating_count: number;
  orders_count: number;
  created_at: string;
  category: Category;
  provider: UserPublic;
}

export interface Review {
  id: number;
  rating: number;
  comment: string;
  created_at: string;
  author: UserPublic;
}

export interface Order {
  id: number;
  requirements: string;
  status: "pending" | "in_progress" | "delivered" | "completed" | "cancelled";
  price_cents: number;
  created_at: string;
  updated_at: string;
  delivered_at: string | null;
  service_id: number;
  buyer_id: number;
  provider_id: number;
  service: Service;
  buyer: UserPublic;
  provider: UserPublic;
  review: Review | null;
}

export interface Transaction {
  id: number;
  kind: "topup" | "purchase" | "earning" | "refund" | "payout";
  amount_cents: number;
  description: string;
  created_at: string;
}

export interface Wallet {
  balance_cents: number;
  transactions: Transaction[];
}

export interface ServiceBrief {
  id: number;
  title: string;
  price_cents: number;
  rating_avg: number;
  delivery_days: number;
  category_name: string;
}

export interface ChatReply {
  reply: string;
  suggestions: ServiceBrief[];
}

export interface Stats {
  services: number;
  providers: number;
  consumers: number;
  orders: number;
  completed_orders: number;
  gmv_cents: number;
  categories: number;
  avg_rating: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}
