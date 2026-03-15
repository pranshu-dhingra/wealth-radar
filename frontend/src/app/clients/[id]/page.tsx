import ClientDetailPage from './client-page';

const CLIENT_IDS = Array.from({ length: 50 }, (_, i) => ({
  id: `CLT${String(i + 1).padStart(3, '0')}`,
}));

export function generateStaticParams() {
  return CLIENT_IDS;
}

export default function Page() {
  return <ClientDetailPage />;
}
