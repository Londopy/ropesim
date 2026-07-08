export default function Footer() {
  return (
    <footer className="border-t border-line py-8">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 font-heading text-xs text-muted">
        <div className="flex gap-5">
          <a href="/quickstart/" className="hover:text-accent">Docs</a>
          <a
            href="https://github.com/Londopy/ropesim"
            className="hover:text-accent"
          >
            GitHub
          </a>
          <a href="https://pypi.org/project/ropesim/" className="hover:text-accent">
            PyPI
          </a>
          <a href="/changelog/" className="hover:text-accent">Changelog</a>
          <a href="/contributing/" className="hover:text-accent">Contributing</a>
        </div>
        <p>built for climbers, by climbers · MIT</p>
      </div>
    </footer>
  );
}
