// Hiển thị Markdown + LaTeX — mục 10 và bảng công nghệ mục 12.
//
// Explain Agent sinh ra $...$ và $$...$$; remark-math tách công thức, rehype-katex
// dựng thành HTML. KaTeX được chọn thay MathJax vì render đồng bộ, không nhấp nháy
// khi chữ đang chảy về theo từng token.

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

export default function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
