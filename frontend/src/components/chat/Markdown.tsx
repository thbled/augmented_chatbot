import { memo } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { ExternalLink } from '../common/ExternalLink';

// Les titres du LLM sont rétrogradés pour respecter la hiérarchie de la page
// (h1 : application, h2 : messages).
const components: Components = {
  h1: ({ children }) => <h3>{children}</h3>,
  h2: ({ children }) => <h3>{children}</h3>,
  h3: ({ children }) => <h4>{children}</h4>,
  h4: ({ children }) => <h4>{children}</h4>,
  a: ({ href, children }) => <ExternalLink href={href}>{children}</ExternalLink>,
  img: () => null,
  table: ({ children }) => (
    <div className="overflow-x-auto">
      <table>{children}</table>
    </div>
  ),
};

const Markdown = memo(function Markdown({ text }: { text: string }) {
  return (
    <div className="prose prose-slate max-w-none text-[0.975rem] leading-relaxed dark:prose-invert prose-headings:mt-4 prose-headings:mb-2 prose-headings:font-semibold prose-h3:text-base prose-h4:text-[0.95rem] prose-p:my-2 prose-a:text-brand-700 prose-a:underline-offset-2 prose-strong:font-semibold prose-ul:my-2 prose-li:my-0.5 dark:prose-a:text-brand-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
});

export default Markdown;
