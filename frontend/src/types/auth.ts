export interface UserPublic {
  id: string
  username: string
  created_at: string
}

export interface LoginInput {
  username: string
  password: string
}
