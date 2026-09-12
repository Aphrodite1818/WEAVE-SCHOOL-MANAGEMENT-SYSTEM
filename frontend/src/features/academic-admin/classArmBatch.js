export async function createClassArms(
  createClass,
  academicLevelId,
  armLabelIds,
  extraPayload = {},
) {
  const created = [];
  const failed = [];
  for (const armLabelId of [...new Set(armLabelIds)]) {
    try {
      created.push(
        await createClass({
          academic_level_id: academicLevelId,
          arm_label_id: armLabelId,
          teacher_membership_id: null,
          ...extraPayload,
        }),
      );
    } catch (error) {
      failed.push({ armLabelId, error });
    }
  }
  return { created, failed };
}
