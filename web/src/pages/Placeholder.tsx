export function Placeholder({ title }: { title: string }) {
  return (
    <>
      <div className="page-head">
        <h1>{title}</h1>
      </div>
      <p className="muted">This page is not built yet. The filters carry over from the Overview.</p>
    </>
  );
}
