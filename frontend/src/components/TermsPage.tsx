import { Link } from "react-router";

export function TermsPage() {
  return (
    <div className="min-h-screen bg-bg">
      <header className="flex items-center h-12 px-4 bg-surface border-b border-border">
        <span className="text-sm font-semibold text-text mr-6">OpenGraph Intel</span>
        <nav className="flex items-center gap-4">
          <Link to="/" className="text-sm text-text-muted hover:text-text">
            Home
          </Link>
          <Link to="/privacy" className="text-sm text-text-muted hover:text-text">
            Privacy Policy
          </Link>
        </nav>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-xl font-semibold text-text mb-6">Terms of Use</h1>

        <div className="flex flex-col gap-6 text-sm text-text-muted leading-relaxed">
          <section>
            <h2 className="text-base font-medium text-text mb-2">1. Acceptance of Terms</h2>
            <p>
              By accessing or using OpenGraph Intel, you agree to be bound by these Terms of
              Use. If you do not agree to these terms, please do not use the service.
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">2. User Accounts</h2>
            <p>
              You are responsible for maintaining the confidentiality of your account credentials and
              for all activities that occur under your account. You must provide accurate and complete
              information when creating an account and keep it up to date. You must notify us
              immediately of any unauthorized use of your account.
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">3. Acceptable Use</h2>
            <p>You agree not to:</p>
            <ul className="list-disc list-inside mt-2 flex flex-col gap-1">
              <li>Use the service for any unlawful purpose or in violation of any applicable laws</li>
              <li>Attempt to gain unauthorized access to other users' accounts or data</li>
              <li>Interfere with or disrupt the service or its infrastructure</li>
              <li>Upload or transmit malicious code or content</li>
              <li>Use the service to harass, abuse, or harm others</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">4. Intellectual Property</h2>
            <p>
              OpenGraph Intel is open source software licensed under the GNU Affero General Public License v3
              (AGPLv3). You may use, modify, and distribute the software in accordance with the terms
              of that license. User-generated content remains the property of its respective owners.
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">5. Disclaimers</h2>
            <p>
              The service is provided "as is" and "as available" without warranties of any kind,
              whether express or implied, including but not limited to implied warranties of
              merchantability, fitness for a particular purpose, and non-infringement. We do not
              warrant that the service will be uninterrupted, error-free, or secure.
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">6. Limitation of Liability</h2>
            <p>
              To the maximum extent permitted by law, OpenGraph Intel and its contributors shall not be liable
              for any indirect, incidental, special, consequential, or punitive damages, or any loss
              of profits or revenues, whether incurred directly or indirectly, or any loss of data,
              use, goodwill, or other intangible losses resulting from your use of the service.
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">7. Termination</h2>
            <p>
              We reserve the right to suspend or terminate your access to the service at any time,
              with or without cause and with or without notice. Upon termination, your right to use
              the service will immediately cease.
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">8. Governing Law</h2>
            <p>
              These terms shall be governed by and construed in accordance with applicable law. Any
              disputes arising under these terms shall be resolved in the appropriate courts of the
              applicable jurisdiction.
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">9. Changes to Terms</h2>
            <p>
              We may update these terms from time to time. Continued use of the service after changes
              constitutes acceptance of the revised terms. We encourage you to review these terms
              periodically.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
