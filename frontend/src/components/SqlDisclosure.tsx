interface SqlDisclosureProps {
  sql: string;
}

export default function SqlDisclosure({ sql }: SqlDisclosureProps) {
  return (
    <details className="mt-2 text-sm">
      <summary className="cursor-pointer text-gray-500 hover:text-gray-700 select-none">
        Show SQL
      </summary>
      <pre className="mt-1 p-2 bg-gray-100 rounded text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all">
        <code>{sql}</code>
      </pre>
    </details>
  );
}
