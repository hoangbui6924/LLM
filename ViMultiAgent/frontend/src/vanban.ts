// Dọn chữ trước khi đưa lên giao diện.
//
// Thẻ "Lưu ý thường gặp" là chỗ duy nhất KHÔNG dựng công thức bằng KaTeX: nó
// nằm ở cột phụ, mỗi dòng chỉ một câu ngắn, dựng công thức ở đó làm dòng chữ
// cao thấp lộn xộn. Nhưng model vẫn quen tay bọc cả số trần trong `$...$`, nên
// phải hạ LaTeX xuống chữ thường đọc được: `$2^{x+1}$` -> `2^(x+1)`, `$12$` -> `12`.
//
// Nguyên tắc: giữ những ký hiệu học sinh vẫn viết tay được (^, /, ×, √, π, ≤),
// bỏ hết phần cú pháp của LaTeX ($ \ { }).

/** Lệnh LaTeX -> ký tự Unicode tương đương. Cái nào không có trong bảng thì chỉ
 *  bị bóc dấu `\` (ví dụ `\log` -> `log`), vì tên lệnh phần lớn đã là ký hiệu
 *  toán đọc được. */
const KY_HIEU: Record<string, string> = {
  times: "×", cdot: "·", div: ":", pm: "±", mp: "∓",
  leq: "≤", le: "≤", geq: "≥", ge: "≥", neq: "≠", ne: "≠",
  approx: "≈", equiv: "≡", sim: "~", propto: "∝",
  to: "→", rightarrow: "→", Rightarrow: "⇒", leftrightarrow: "↔", implies: "⇒",
  infty: "∞", in: "∈", notin: "∉", cup: "∪", cap: "∩", subset: "⊂",
  forall: "∀", exists: "∃", emptyset: "∅",
  sum: "Σ", prod: "Π", int: "∫", partial: "∂", nabla: "∇",
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", Delta: "Δ",
  epsilon: "ε", varepsilon: "ε", zeta: "ζ", eta: "η",
  theta: "θ", lambda: "λ", mu: "μ", nu: "ν", xi: "ξ",
  pi: "π", rho: "ρ", sigma: "σ", Sigma: "Σ", tau: "τ",
  phi: "φ", varphi: "φ", Phi: "Φ", omega: "ω", Omega: "Ω",
  circ: "°", degree: "°", angle: "∠", perp: "⊥", parallel: "∥",
  ldots: "…", dots: "…", cdots: "…", quad: " ", qquad: " ",
  left: "", right: "", displaystyle: "", limits: "",
};

/** Hạ một đoạn có LaTeX xuống chữ thường đọc được. */
export function lamSachToan(s: string): string {
  let t = s;

  // 1. Vỏ công thức: $...$, $$...$$, \(...\), \[...\]
  t = t.replace(/\$\$?/g, "").replace(/\\[()[\]]/g, "");

  // 2. Bọc chữ: \text{...}, \mathrm{...} — chỉ giữ ruột
  t = t.replace(/\\(?:text|textbf|textit|mathrm|mathbf|mathit|operatorname)\s*\{([^{}]*)\}/g, "$1");

  // 3. Phân số và căn. Lặp vài vòng cho trường hợp lồng nhau — LaTeX của bài
  //    THPT hiếm khi lồng quá 3 tầng.
  for (let i = 0; i < 3; i++) {
    t = t.replace(/\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, (_, a: string, b: string) =>
      `${bocNgoac(a)}/${bocNgoac(b)}`,
    );
    t = t.replace(/\\sqrt\s*\{([^{}]*)\}/g, (_, a: string) => `√${bocNgoac(a)}`);
  }

  // 4. Mũ và chỉ số: bỏ ngoặc nhọn, giữ lại ^ và _ vì học sinh vẫn viết như vậy
  t = t.replace(/\^\s*\{([^{}]*)\}/g, (_, a: string) => `^${bocNgoac(a)}`);
  t = t.replace(/_\s*\{([^{}]*)\}/g, (_, a: string) => `_${bocNgoac(a)}`);

  // 5. Khoảng trắng giả của LaTeX: \, \; \! \:
  t = t.replace(/\\[,;:!]/g, " ");

  // 6. Các lệnh còn lại
  t = t.replace(/\\([a-zA-Z]+)/g, (_, ten: string) =>
    ten in KY_HIEU ? KY_HIEU[ten] : ten,
  );

  // 7. Rác còn sót: ngoặc nhọn, dấu nhấn Markdown, dấu gạch chéo lẻ
  t = t.replace(/[{}]/g, "").replace(/\*+/g, "").replace(/`/g, "").replace(/\\/g, "");

  // 8. Gom khoảng trắng, kéo dấu câu về sát chữ
  return t.replace(/\s+/g, " ").replace(/\s+([,.;:)])/g, "$1").replace(/\(\s+/g, "(").trim();
}

/** Chỉ thêm ngoặc khi ruột có phép tính bên trong — `2^10` và `v_max` không cần,
 *  nhưng `2^(x+1)` thì có, không thì đọc thành `2^x + 1`. */
function bocNgoac(s: string): string {
  const g = s.trim();
  return /^[\wα-ωΑ-Ω.,]+$/u.test(g) ? g : `(${g})`;
}

const DAU_TIENG_VIET =
  /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

const TU_TIENG_ANH =
  /\b(the|this|that|these|is|are|was|were|we|you|they|have|has|had|step|first|second|then|therefore|thus|because|since|when|while|should|must|need|use|using|used|forget|forgetting|remember|check|value|note|error|mistake|common|make|sure|not|don't|doesn't|avoid|instead|of|to|for|and|with|in|on|by|if|but|so|it|its)\b/gi;

/** Dòng lưu ý viết bằng tiếng Anh thì bỏ hẳn, không cố dịch.
 *
 * qwen3:4b thỉnh thoảng tuột về tiếng Anh ở mục cuối lời giảng. Một câu tiếng
 * Việt gần như luôn có dấu; câu không dấu mà lại chứa từ nối tiếng Anh thì gần
 * như chắc chắn là tiếng Anh. Dịch máy offline sẽ sai thuật ngữ, còn để nguyên
 * thì học sinh đọc không được — nên bỏ là lựa chọn trung thực nhất. */
export function laTiengAnh(s: string): boolean {
  if (DAU_TIENG_VIET.test(s)) return false;
  return (s.match(TU_TIENG_ANH) ?? []).length >= 2;
}
