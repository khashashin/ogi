export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  owner_id: string | null;
  is_public: boolean;
  role?: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  is_public?: boolean;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  is_public?: boolean;
}
