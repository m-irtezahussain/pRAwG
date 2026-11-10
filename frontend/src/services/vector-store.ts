export type VectorStoreProvider =
  | "chroma_self_hosted"
  | "chroma_cloud"
  | "pinecone_cloud"
  | "qdrant_self_hosted"
  | "qdrant_cloud";

type BaseConnection = { provider: VectorStoreProvider };

export type VectorStoreConnectionInput =
  | (BaseConnection & { provider: "chroma_self_hosted"; endpoint: string; collection: string; tenant: string; database: string; auth_token?: string })
  | (BaseConnection & { provider: "chroma_cloud"; api_key: string; tenant: string; database: string; collection: string })
  | (BaseConnection & { provider: "pinecone_cloud"; api_key: string; index_name: string; namespace: string })
  | (BaseConnection & { provider: "qdrant_self_hosted"; endpoint: string; collection: string; api_key?: string })
  | (BaseConnection & { provider: "qdrant_cloud"; endpoint: string; api_key: string; collection: string });

export type VectorStoreConnection = {
  provider: VectorStoreProvider;
  label: string;
  collection: string;
  connected: boolean;
};

export type VectorCollection = {
  name: string;
  kind: "collection" | "namespace";
  records: number | null;
  active: boolean;
};

export type VectorCollectionList = {
  provider: VectorStoreProvider;
  collections: VectorCollection[];
};

export type MetadataValue = string | number | boolean | null | MetadataValue[] | { [key: string]: MetadataValue };

export type VectorChunk = {
  id: string;
  text: string;
  metadata: Record<string, MetadataValue>;
  score: number | null;
};

export type VectorChunkPage = {
  collection: string;
  chunks: VectorChunk[];
  total: number | null;
  next_cursor: string | null;
};

export type CollectionSearchMode = "similarity" | "text";

export type CollectionSearchResult = {
  collection: string;
  mode: CollectionSearchMode;
  chunks: VectorChunk[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

async function parseResponse(response: Response): Promise<VectorStoreConnection> {
  if (response.ok) return response.json() as Promise<VectorStoreConnection>;
  let message = "Unable to connect to the vector store.";
  try {
    const body = await response.json() as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === "string") message = body.detail;
    else if (Array.isArray(body.detail)) message = body.detail[0]?.msg ?? message;
  } catch {
    // Keep the safe fallback when the API does not return JSON.
  }
  throw new Error(message);
}

export async function getVectorStoreConnection(): Promise<VectorStoreConnection> {
  const response = await fetch(`${API_URL}/api/v1/vector-store/connection`, { cache: "no-store" });
  return parseResponse(response);
}

export async function getVectorStoreCollections(): Promise<VectorCollectionList> {
  const response = await fetch(`${API_URL}/api/v1/vector-store/collections`, { cache: "no-store" });
  if (response.ok) return response.json() as Promise<VectorCollectionList>;
  let message = "Unable to load collections from the connected database.";
  try {
    const body = await response.json() as { detail?: string };
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    // Preserve the safe fallback for non-JSON proxy responses.
  }
  throw new Error(message);
}

export async function connectVectorStore(input: VectorStoreConnectionInput): Promise<VectorStoreConnection> {
  const response = await fetch(`${API_URL}/api/v1/vector-store/connections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseResponse(response);
}

async function parseCollectionResponse<T>(response: Response, fallback: string): Promise<T> {
  if (response.ok) return response.json() as Promise<T>;
  let message = fallback;
  try {
    const body = await response.json() as { detail?: string };
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    // Preserve the safe fallback for non-JSON proxy responses.
  }
  throw new Error(message);
}

export async function getCollectionChunks(collection: string, cursor?: string): Promise<VectorChunkPage> {
  const params = new URLSearchParams({ limit: "25" });
  if (cursor) params.set("cursor", cursor);
  const response = await fetch(`${API_URL}/api/v1/vector-store/collections/${encodeURIComponent(collection)}/chunks?${params}`, { cache: "no-store" });
  return parseCollectionResponse(response, "Unable to load chunks from this collection.");
}

export async function searchCollectionChunks(
  collection: string,
  query: string,
  mode: CollectionSearchMode,
): Promise<CollectionSearchResult> {
  const response = await fetch(`${API_URL}/api/v1/vector-store/collections/${encodeURIComponent(collection)}/chunks/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, mode, limit: 50 }),
  });
  return parseCollectionResponse(response, "Unable to search this collection.");
}

export async function deleteCollectionChunk(collection: string, chunkId: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/vector-store/collections/${encodeURIComponent(collection)}/chunks/${encodeURIComponent(chunkId)}`, {
    method: "DELETE",
  });
  await parseCollectionResponse<{ deleted: boolean }>(response, "Unable to delete this chunk.");
}
