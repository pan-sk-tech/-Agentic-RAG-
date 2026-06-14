from fin_compliance.parsers.claim_parser import ClaimParser


class ExcelParser:
    """Parse CSV/TSV/XLSX reimbursement sheets into ReimbursementClaim."""

    def parse(self, path):
        return ClaimParser().parse(path)
