export function filterStudentCommentRows(rows = [], search = "") {
  const query = String(search || "").trim().toLocaleLowerCase();
  if (!query) return rows;
  return rows.filter((row) =>
    [row?.student_name, row?.admission_number].some((value) =>
      String(value || "").toLocaleLowerCase().includes(query),
    ),
  );
}

