/** Google Picker loader — the native Drive chooser for moodboards.
 *  Works under the drive.file scope: the app only ever gains access to the
 *  files the producer explicitly picks here. */

export interface PickedFile {
  id: string;
  name: string;
  mime_type: string;
}

let gapiReady: Promise<void> | null = null;

function loadPickerLib(): Promise<void> {
  if (gapiReady) return gapiReady;
  gapiReady = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://apis.google.com/js/api.js";
    s.onload = () => (window as any).gapi.load("picker", () => resolve());
    s.onerror = () => reject(new Error("Could not load Google Picker"));
    document.head.appendChild(s);
  });
  return gapiReady;
}

export async function openDrivePicker(
  cfg: { access_token: string; api_key: string },
  onPicked: (files: PickedFile[]) => void,
): Promise<void> {
  await loadPickerLib();
  const g = (window as any).google;
  const picker = new g.picker.PickerBuilder()
    .setOAuthToken(cfg.access_token)
    .setDeveloperKey(cfg.api_key)
    .setTitle("Pick a moodboard — Slides, PDF or images")
    .addView(new g.picker.DocsView(g.picker.ViewId.PRESENTATIONS))
    .addView(new g.picker.DocsView(g.picker.ViewId.PDFS))
    .addView(new g.picker.DocsView(g.picker.ViewId.DOCS_IMAGES))
    .enableFeature(g.picker.Feature.MULTISELECT_ENABLED)
    .setCallback((data: any) => {
      if (data.action === g.picker.Action.PICKED) {
        onPicked(
          (data.docs ?? []).map((d: any) => ({
            id: d.id,
            name: d.name,
            mime_type: d.mimeType,
          })),
        );
      }
    })
    .build();
  picker.setVisible(true);
}
