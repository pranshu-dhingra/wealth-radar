export function generateStaticParams() {
  return Array.from({ length: 50 }, (_, i) => ({
    id: `CLT${String(i + 1).padStart(3, '0')}`,
  }));
}

export default function MeetingPrepPage({ params }: { params: { id: string } }) {
  return <div>Meeting prep for client {params.id} — coming soon</div>;
}
