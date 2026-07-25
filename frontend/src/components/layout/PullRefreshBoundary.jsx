function PullRefreshBoundary({ children }) {
  return (
    <div
      className="contents"
      onTouchStartCapture={(event) => event.stopPropagation()}
    >
      {children}
    </div>
  );
}

export default PullRefreshBoundary;
