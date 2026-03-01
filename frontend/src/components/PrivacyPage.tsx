import { Link } from "react-router";

export function PrivacyPage() {
  return (
    <div className="min-h-screen bg-bg">
      <header className="flex items-center h-12 px-4 bg-surface border-b border-border">
        <span className="text-sm font-semibold text-text mr-6">OGI</span>
        <nav className="flex items-center gap-4">
          <Link to="/" className="text-sm text-text-muted hover:text-text">
            Home
          </Link>
          <Link to="/terms" className="text-sm text-text-muted hover:text-text">
            Terms of Use
          </Link>
        </nav>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-xl font-semibold text-text mb-6">Privacy Policy</h1>

        <div className="flex flex-col gap-6 text-sm text-text-muted leading-relaxed">
          <section>
            <h2 className="text-base font-medium text-text mb-2">1. Information We Collect</h2>
            <p>We collect the following types of information:</p>
            <ul className="list-disc list-inside mt-2 flex flex-col gap-1">
              <li>
                <strong className="text-text">Account information:</strong> email address and
                authentication credentials when you create an account
              </li>
              <li>
                <strong className="text-text">Usage data:</strong> pages visited, features used, and
                interactions with the service, collected via Google Analytics
              </li>
              <li>
                <strong className="text-text">Project data:</strong> graphs, entities, and other
                content you create within the service
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">2. Authentication</h2>
            <p>
              We use Supabase for user authentication. Your email and password are securely managed
              by Supabase's authentication infrastructure. We do not store your password directly.
              Please refer to{" "}
              <a
                href="https://supabase.com/privacy"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                Supabase's Privacy Policy
              </a>{" "}
              for details on how they handle authentication data.
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">3. Analytics</h2>
            <p>
              We use Google Analytics to collect anonymized usage data to understand how the service
              is used and to improve it. Google Analytics may collect information such as your IP
              address (anonymized), browser type, operating system, pages visited, and session
              duration. Please refer to{" "}
              <a
                href="https://policies.google.com/privacy"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                Google's Privacy Policy
              </a>{" "}
              for details.
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">4. Cookies</h2>
            <p>
              We use cookies and similar technologies for authentication session management and
              analytics. Essential cookies are required for the service to function properly.
              Analytics cookies help us understand usage patterns.
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">5. Data Retention</h2>
            <p>
              We retain your account information and project data for as long as your account is
              active. If you delete your account, we will remove your personal data within a
              reasonable timeframe. Anonymized analytics data may be retained indefinitely.
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">6. Third-Party Services</h2>
            <p>We use the following third-party services that may process your data:</p>
            <ul className="list-disc list-inside mt-2 flex flex-col gap-1">
              <li>
                <strong className="text-text">Supabase</strong> — authentication, database, and
                real-time features
              </li>
              <li>
                <strong className="text-text">Google Analytics</strong> — usage tracking and
                analytics
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">7. Your Rights</h2>
            <p>You have the right to:</p>
            <ul className="list-disc list-inside mt-2 flex flex-col gap-1">
              <li>Access your personal data</li>
              <li>Request correction of inaccurate data</li>
              <li>Request deletion of your data</li>
              <li>Export your data</li>
              <li>Withdraw consent for data processing</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">8. Contact</h2>
            <p>
              If you have questions about this Privacy Policy or wish to exercise your rights, please
              open an issue on our{" "}
              <a
                href="https://github.com/nicholasgasior/ogi"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                GitHub repository
              </a>
              .
            </p>
          </section>

          <section>
            <h2 className="text-base font-medium text-text mb-2">9. Changes to This Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. Continued use of the service after
              changes constitutes acceptance of the revised policy. We encourage you to review this
              policy periodically.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
