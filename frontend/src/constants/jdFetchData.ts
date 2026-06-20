/**
 * JD Auto-Fetch dropdown constants.
 *
 * TOP_COMPANIES — 15 Indian-market companies shown in the company <select>.
 * The "Other..." option is added by UploadZone separately (value="other").
 *
 * TOP_ROLES_BY_GROUP — mirrored from backend/data/role_taxonomy.json.
 * Each entry carries role_family + rank so UploadZone can pass them to the
 * /api/fetch-jd endpoint, which threads them into the alias-expansion layer.
 * rank/role_family are internal join keys — never rendered to the user.
 * generic_title is the only string ever shown in the dropdown.
 */

export interface RoleEntry {
  generic_title: string;
  role_family: string;
  rank: string;
}

export interface RoleGroup {
  label: string;
  roles: RoleEntry[];
}

export const TOP_COMPANIES: string[] = [
  "Amazon",
  "Google",
  "Meta",
  "Microsoft",
  "Flipkart",
  "Swiggy",
  "Zomato",
  "Razorpay",
  "CRED",
  "Meesho",
  "Zepto",
  "PhonePe",
  "Atlassian",
  "Stripe",
  "Infosys",
];

export const TOP_ROLES_BY_GROUP: RoleGroup[] = [
  {
    label: "Engineering",
    roles: [
      { generic_title: "Junior Software Engineer", role_family: "engineering", rank: "junior" },
      { generic_title: "Software Engineer", role_family: "engineering", rank: "mid" },
      { generic_title: "Senior Software Engineer", role_family: "engineering", rank: "senior" },
      { generic_title: "Staff Engineer", role_family: "engineering", rank: "staff" },
      { generic_title: "Engineering Manager", role_family: "engineering", rank: "manager" },
      { generic_title: "Senior Engineering Manager", role_family: "engineering", rank: "senior_manager" },
      { generic_title: "Director of Engineering", role_family: "engineering", rank: "director" },
      { generic_title: "VP of Engineering", role_family: "engineering", rank: "vp" },
    ],
  },
  {
    label: "Product Management",
    roles: [
      { generic_title: "Associate Product Manager", role_family: "product_management", rank: "junior" },
      { generic_title: "Product Manager", role_family: "product_management", rank: "mid" },
      { generic_title: "Senior Product Manager", role_family: "product_management", rank: "senior" },
      { generic_title: "Group Product Manager", role_family: "product_management", rank: "staff" },
      { generic_title: "Director of Product", role_family: "product_management", rank: "manager" },
      { generic_title: "Senior Director of Product", role_family: "product_management", rank: "senior_manager" },
      { generic_title: "VP of Product", role_family: "product_management", rank: "director" },
      { generic_title: "Chief Product Officer", role_family: "product_management", rank: "vp" },
    ],
  },
  {
    label: "Data & Analytics",
    roles: [
      { generic_title: "Junior Data Analyst", role_family: "data_analytics", rank: "junior" },
      { generic_title: "Data Analyst", role_family: "data_analytics", rank: "mid" },
      { generic_title: "Senior Data Analyst", role_family: "data_analytics", rank: "senior" },
      { generic_title: "Lead Data Analyst", role_family: "data_analytics", rank: "staff" },
      { generic_title: "Analytics Manager", role_family: "data_analytics", rank: "manager" },
      { generic_title: "Senior Analytics Manager", role_family: "data_analytics", rank: "senior_manager" },
      { generic_title: "Director of Data & Analytics", role_family: "data_analytics", rank: "director" },
      { generic_title: "VP of Data", role_family: "data_analytics", rank: "vp" },
    ],
  },
  {
    label: "Design",
    roles: [
      { generic_title: "Junior UX/UI Designer", role_family: "design", rank: "junior" },
      { generic_title: "UX/UI Designer", role_family: "design", rank: "mid" },
      { generic_title: "Senior UX/UI Designer", role_family: "design", rank: "senior" },
      { generic_title: "Lead Designer", role_family: "design", rank: "staff" },
      { generic_title: "Design Manager", role_family: "design", rank: "manager" },
      { generic_title: "Senior Design Manager", role_family: "design", rank: "senior_manager" },
      { generic_title: "Director of Design", role_family: "design", rank: "director" },
      { generic_title: "VP of Design", role_family: "design", rank: "vp" },
    ],
  },
  {
    label: "Marketing",
    roles: [
      { generic_title: "Marketing Associate", role_family: "marketing", rank: "junior" },
      { generic_title: "Marketing Manager", role_family: "marketing", rank: "mid" },
      { generic_title: "Senior Marketing Manager", role_family: "marketing", rank: "senior" },
      { generic_title: "Marketing Lead", role_family: "marketing", rank: "staff" },
      { generic_title: "Associate Director of Marketing", role_family: "marketing", rank: "manager" },
      { generic_title: "Director of Marketing", role_family: "marketing", rank: "senior_manager" },
      { generic_title: "Senior Director of Marketing", role_family: "marketing", rank: "director" },
      { generic_title: "VP of Marketing", role_family: "marketing", rank: "vp" },
    ],
  },
  {
    label: "Operations",
    roles: [
      { generic_title: "Operations Associate", role_family: "operations", rank: "junior" },
      { generic_title: "Operations Manager", role_family: "operations", rank: "mid" },
      { generic_title: "Senior Operations Manager", role_family: "operations", rank: "senior" },
      { generic_title: "Operations Lead", role_family: "operations", rank: "staff" },
      { generic_title: "Associate Director of Operations", role_family: "operations", rank: "manager" },
      { generic_title: "Director of Operations", role_family: "operations", rank: "senior_manager" },
      { generic_title: "Senior Director of Operations", role_family: "operations", rank: "director" },
      { generic_title: "VP of Operations", role_family: "operations", rank: "vp" },
    ],
  },
  {
    label: "Consulting",
    roles: [
      { generic_title: "Business Analyst", role_family: "consulting", rank: "junior" },
      { generic_title: "Consultant", role_family: "consulting", rank: "mid" },
      { generic_title: "Senior Consultant", role_family: "consulting", rank: "senior" },
      { generic_title: "Engagement Manager", role_family: "consulting", rank: "staff" },
      { generic_title: "Manager", role_family: "consulting", rank: "manager" },
      { generic_title: "Senior Manager", role_family: "consulting", rank: "senior_manager" },
      { generic_title: "Principal", role_family: "consulting", rank: "director" },
      { generic_title: "Partner", role_family: "consulting", rank: "vp" },
    ],
  },
  {
    label: "Finance",
    roles: [
      { generic_title: "Financial Analyst", role_family: "finance", rank: "junior" },
      { generic_title: "Senior Financial Analyst", role_family: "finance", rank: "mid" },
      { generic_title: "Finance Manager", role_family: "finance", rank: "senior" },
      { generic_title: "Senior Finance Manager", role_family: "finance", rank: "staff" },
      { generic_title: "Associate Director of Finance", role_family: "finance", rank: "manager" },
      { generic_title: "Director of Finance", role_family: "finance", rank: "senior_manager" },
      { generic_title: "VP of Finance", role_family: "finance", rank: "director" },
      { generic_title: "Chief Financial Officer", role_family: "finance", rank: "vp" },
    ],
  },
  {
    label: "Human Resources",
    roles: [
      { generic_title: "HR Associate", role_family: "hr", rank: "junior" },
      { generic_title: "HR Business Partner", role_family: "hr", rank: "mid" },
      { generic_title: "Senior HR Business Partner", role_family: "hr", rank: "senior" },
      { generic_title: "HR Lead", role_family: "hr", rank: "staff" },
      { generic_title: "Associate Director of HR", role_family: "hr", rank: "manager" },
      { generic_title: "Director of HR", role_family: "hr", rank: "senior_manager" },
      { generic_title: "VP of HR", role_family: "hr", rank: "director" },
      { generic_title: "Chief Human Resources Officer", role_family: "hr", rank: "vp" },
    ],
  },
  {
    label: "Sales",
    roles: [
      { generic_title: "Sales Development Representative", role_family: "sales", rank: "junior" },
      { generic_title: "Account Executive", role_family: "sales", rank: "mid" },
      { generic_title: "Senior Account Executive", role_family: "sales", rank: "senior" },
      { generic_title: "Key Account Manager", role_family: "sales", rank: "staff" },
      { generic_title: "Sales Manager", role_family: "sales", rank: "manager" },
      { generic_title: "Senior Sales Manager", role_family: "sales", rank: "senior_manager" },
      { generic_title: "Director of Sales", role_family: "sales", rank: "director" },
      { generic_title: "VP of Sales", role_family: "sales", rank: "vp" },
    ],
  },
];

/** Flat lookup: generic_title → RoleEntry. Used in UploadZone to find
 *  role_family + rank from a selected dropdown value. */
export function findRoleEntry(genericTitle: string): RoleEntry | null {
  for (const group of TOP_ROLES_BY_GROUP) {
    const found = group.roles.find((r) => r.generic_title === genericTitle);
    if (found) return found;
  }
  return null;
}
