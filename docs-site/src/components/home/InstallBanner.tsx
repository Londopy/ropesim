import CopyButton from '@/components/shared/CopyButton';

export default function InstallBanner() {
  return (
    <section className="border-y border-line bg-surface/60 py-16 text-center">
      <div className="mx-auto inline-flex items-center gap-4 rounded-xl border border-line bg-codebg px-6 py-4">
        <code className="font-code text-lg text-bright">
          <span className="text-muted">$</span> pip install ropesim
        </code>
        <CopyButton text="pip install ropesim" />
      </div>
      <p className="mt-4 font-heading text-xs text-muted">
        desktop app? grab the installer from{' '}
        <a
          href="https://github.com/Londopy/ropesim/releases"
          className="text-accent underline decoration-accent-dim underline-offset-2"
        >
          GitHub Releases
        </a>{' '}
        — no Python required
      </p>
      <div className="mt-5 flex justify-center gap-2">
        <img
          src="https://img.shields.io/pypi/v/ropesim?color=7ecf45&labelColor=171c18"
          alt="PyPI version"
        />
        <img
          src="https://img.shields.io/badge/license-MIT-7ecf45?labelColor=171c18"
          alt="MIT license"
        />
        <img
          src="https://img.shields.io/pypi/pyversions/ropesim?color=7ecf45&labelColor=171c18"
          alt="Python versions"
        />
      </div>
    </section>
  );
}
