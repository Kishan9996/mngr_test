export interface UserInfo {
  user_id: string;
  email: string;
  org_id: number;
  org_name: string;
  role: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}
