import { api } from "@/lib/api";
import type { Resume } from "@/lib/resume/types";

interface ResumeApiShape {
  id: string;
  user_id: string;
  title: string;
  template_id: string;
  data: Resume["data"];
  styles: Resume["styles"];
  source: "new" | "upload";
  uploaded_file_path: string | null;
  created_at: string;
  updated_at: string;
}

function fromApi(r: ResumeApiShape): Resume {
  return {
    id: r.id,
    userId: r.user_id,
    title: r.title,
    templateId: r.template_id,
    data: r.data,
    styles: r.styles,
    source: r.source,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  };
}

export const resumeApi = {
  list: async (): Promise<Resume[]> => (await api.get<ResumeApiShape[]>("/resumes")).map(fromApi),

  get: async (id: string): Promise<Resume> => fromApi(await api.get<ResumeApiShape>(`/resumes/${id}`)),

  create: async (payload: {
    title: string;
    template_id: string;
    data: Resume["data"];
    styles: Resume["styles"];
  }): Promise<Resume> => fromApi(await api.post<ResumeApiShape>("/resumes", payload)),

  update: async (
    id: string,
    payload: Partial<{
      title: string;
      template_id: string;
      data: Resume["data"];
      styles: Resume["styles"];
    }>
  ): Promise<Resume> => fromApi(await api.put<ResumeApiShape>(`/resumes/${id}`, payload)),

  remove: (id: string) => api.delete(`/resumes/${id}`),

  upload: async (file: File): Promise<Resume> =>
    fromApi(await api.upload<ResumeApiShape>("/resumes/upload", file)),
};
