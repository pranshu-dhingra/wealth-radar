import MeetingPrepPage from "./meeting-prep-page";

export function generateStaticParams() {
  return Array.from({ length: 50 }, (_, i) => ({
    id: `CLT${String(i + 1).padStart(3, '0')}`,
  }));
}

export default function Page() {
  return <MeetingPrepPage />;
}
