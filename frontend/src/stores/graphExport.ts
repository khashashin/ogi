let exportGraphHandler: (() => Promise<void>) | null = null;

export function setGraphExportHandler(handler: (() => Promise<void>) | null): void {
  exportGraphHandler = handler;
}

export async function exportGraphImage(): Promise<void> {
  if (!exportGraphHandler) {
    throw new Error("Graph export is not available");
  }
  await exportGraphHandler();
}
