function PageHeader({ eyebrow, title, actions }) {
  return (
    <div className="page-header lg:items-end">
      <div className="min-w-0 flex-1">
        {eyebrow && (
          <p className="text-xs font-bold uppercase tracking-wide text-primary">
            {eyebrow}
          </p>
        )}
        <h1 className="page-title">
          {title}
        </h1>
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </div>
  );
}

export default PageHeader;
