export interface CountryCode {
  country: string;
  iso2: string;
  dialCode: string;
}

// Common dialing codes, sorted alphabetically by country name.
export const COUNTRY_CODES: CountryCode[] = [
  { country: "Afghanistan", iso2: "AF", dialCode: "+93" },
  { country: "Australia", iso2: "AU", dialCode: "+61" },
  { country: "Bangladesh", iso2: "BD", dialCode: "+880" },
  { country: "Brazil", iso2: "BR", dialCode: "+55" },
  { country: "Canada", iso2: "CA", dialCode: "+1" },
  { country: "China", iso2: "CN", dialCode: "+86" },
  { country: "Egypt", iso2: "EG", dialCode: "+20" },
  { country: "France", iso2: "FR", dialCode: "+33" },
  { country: "Germany", iso2: "DE", dialCode: "+49" },
  { country: "India", iso2: "IN", dialCode: "+91" },
  { country: "Indonesia", iso2: "ID", dialCode: "+62" },
  { country: "Ireland", iso2: "IE", dialCode: "+353" },
  { country: "Italy", iso2: "IT", dialCode: "+39" },
  { country: "Japan", iso2: "JP", dialCode: "+81" },
  { country: "Kenya", iso2: "KE", dialCode: "+254" },
  { country: "Malaysia", iso2: "MY", dialCode: "+60" },
  { country: "Mexico", iso2: "MX", dialCode: "+52" },
  { country: "Nepal", iso2: "NP", dialCode: "+977" },
  { country: "Netherlands", iso2: "NL", dialCode: "+31" },
  { country: "New Zealand", iso2: "NZ", dialCode: "+64" },
  { country: "Nigeria", iso2: "NG", dialCode: "+234" },
  { country: "Pakistan", iso2: "PK", dialCode: "+92" },
  { country: "Philippines", iso2: "PH", dialCode: "+63" },
  { country: "Poland", iso2: "PL", dialCode: "+48" },
  { country: "Russia", iso2: "RU", dialCode: "+7" },
  { country: "Saudi Arabia", iso2: "SA", dialCode: "+966" },
  { country: "Singapore", iso2: "SG", dialCode: "+65" },
  { country: "South Africa", iso2: "ZA", dialCode: "+27" },
  { country: "South Korea", iso2: "KR", dialCode: "+82" },
  { country: "Spain", iso2: "ES", dialCode: "+34" },
  { country: "Sri Lanka", iso2: "LK", dialCode: "+94" },
  { country: "Sweden", iso2: "SE", dialCode: "+46" },
  { country: "Switzerland", iso2: "CH", dialCode: "+41" },
  { country: "Thailand", iso2: "TH", dialCode: "+66" },
  { country: "United Arab Emirates", iso2: "AE", dialCode: "+971" },
  { country: "United Kingdom", iso2: "GB", dialCode: "+44" },
  { country: "United States", iso2: "US", dialCode: "+1" },
  { country: "Vietnam", iso2: "VN", dialCode: "+84" },
];
