import { useEffect, useState } from "react";
import { api } from "../api/client";

interface ProtectedMediaImageProps {
  projectId?: string | null;
  entityId?: string | null;
  src?: string | null;
  alt?: string;
  className?: string;
  onError?: () => void;
}

export function ProtectedMediaImage({
  projectId,
  entityId,
  src,
  alt = "",
  className,
  onError,
}: ProtectedMediaImageProps) {
  const fallbackSrc = src?.trim() || null;
  const [resolvedSrc, setResolvedSrc] = useState<string | null>(fallbackSrc);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    async function resolveImage() {
      if (projectId && entityId) {
        try {
          const blob = await api.entities.fetchPersonImage(projectId, entityId);
          if (cancelled) return;
          objectUrl = URL.createObjectURL(blob);
          setResolvedSrc(objectUrl);
          return;
        } catch {
          if (!cancelled) {
            if (fallbackSrc && !fallbackSrc.startsWith("/api/v1/")) {
              setResolvedSrc(fallbackSrc);
            } else {
              setResolvedSrc(null);
              onError?.();
            }
          }
          return;
        }
      }

      if (!cancelled) {
        setResolvedSrc(fallbackSrc);
      }
    }

    void resolveImage();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [entityId, fallbackSrc, onError, projectId]);

  if (!resolvedSrc) return null;

  return <img src={resolvedSrc} alt={alt} className={className} onError={onError} />;
}
