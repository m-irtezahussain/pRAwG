export type IngestedDocument = {
  document_id: string;
  filename: string;
  chunks: number;
  characters: number;
  ocr_used: boolean;
  stored: boolean;
  metadata: Record<string, string>;
};

export type StoredDocument = {
  document_id: string;
  filename: string;
  size: number;
  content_type: string;
  collection: string;
  chunks: number;
  uploaded_at: string;
  metadata: Record<string, string>;
};

export type DocumentUploadOptions = {
  filename: string;
  metadata: Record<string, string>;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export async function uploadDocument(file: File, options: DocumentUploadOptions): Promise<IngestedDocument> {
  const body = new FormData();
  body.append("file", file, file.name);
  body.append("filename", options.filename);
  body.append("metadata", JSON.stringify(options.metadata));
  const response = await fetch(`${API_URL}/api/v1/documents`, { method: "POST", body });
  if (response.ok) return response.json() as Promise<IngestedDocument>;

  let message = "We couldn't add this document. Check the file and try again.";
  try {
    const payload = await response.json() as { detail?: string };
    if (typeof payload.detail === "string") message = payload.detail;
  } catch {
    // Proxies may return HTML; retain the safe fallback message.
  }
  throw new Error(message);
}

export async function getStoredDocuments(): Promise<StoredDocument[]> {
  const response = await fetch(`${API_URL}/api/v1/documents`, { cache: "no-store" });
  if (response.ok) {
    const payload = await response.json() as { documents: StoredDocument[] };
    return payload.documents;
  }
  throw new Error("We couldn't load your stored documents.");
}

export function storedDocumentDownloadUrl(documentId: string): string {
  return `${API_URL}/api/v1/documents/${encodeURIComponent(documentId)}/content`;
}
