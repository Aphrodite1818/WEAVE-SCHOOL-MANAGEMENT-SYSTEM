export default function AICreditCompletePage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <section aria-labelledby="ai-credit-completion-title" className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-10 dark:border-slate-800 dark:bg-slate-900">
        <p className="mb-4 text-sm font-semibold">Weave</p>
        <h1 id="ai-credit-completion-title" className="text-2xl font-semibold">AI credit checkout</h1>
        <p className="mt-4 text-slate-600 dark:text-slate-300">
          You can return to Weave CBT to check your purchase status and credit balance.
          Credits are added automatically once your payment is confirmed. This may take a few moments.
        </p>
        <p className="mt-4 text-sm text-slate-600 dark:text-slate-300">
          This page does not confirm payment success. If your purchase is still pending,
          use the verification option in Weave CBT. You can close this tab when you are ready.
        </p>
      </section>
    </main>
  );
}
