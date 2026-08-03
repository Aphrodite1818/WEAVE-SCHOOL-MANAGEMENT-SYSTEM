function PublicLayout({ children }) {
  return (
    <div
      className="public-page-shell min-h-[100dvh] bg-background text-text"
      data-pwa-scroll-root="true"
    >
      {children}
    </div>
  );
}

export default PublicLayout;
