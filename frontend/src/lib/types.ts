export type Source = {
  n: number;
  ref: string;
  act: string;
  section_number: string | null;
  title: string | null;
  page: number | null;
  snippet: string;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  verified: boolean | null;
  streaming?: boolean;
  error?: string;
};

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ServerMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  verified: boolean | null;
  created_at: string;
};

export type ChatEvent =
  | { type: "meta"; conversation_id: string }
  | { type: "status"; step: string }
  | { type: "reset" }
  | { type: "token"; text: string }
  | { type: "done"; message_id: number | null; sources: Source[]; verified: boolean | null }
  | { type: "error"; message: string };

export const LANGUAGES: { value: string; label: string }[] = [
  { value: "auto", label: "Auto-detect" },
  { value: "English", label: "English" },
  { value: "Hindi", label: "हिन्दी" },
  { value: "Bengali", label: "বাংলা" },
  { value: "Marathi", label: "मराठी" },
  { value: "Telugu", label: "తెలుగు" },
  { value: "Tamil", label: "தமிழ்" },
  { value: "Gujarati", label: "ગુજરાતી" },
  { value: "Kannada", label: "ಕನ್ನಡ" },
  { value: "Malayalam", label: "മലയാളം" },
];

export const STATUS_LABELS: Record<string, string> = {
  connecting: "Connecting…",
  waking: "Waking up the server (free hosting). This can take up to a minute…",
  analyzing: "Understanding your question…",
  searching: "Searching the Acts…",
  checking: "Checking which provisions apply…",
  writing: "Writing the answer…",
  verifying: "Verifying against the sources…",
};
