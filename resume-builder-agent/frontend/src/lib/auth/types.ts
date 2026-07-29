export type Gender = "male" | "female" | "prefer_not_to_say";
export type AddressType = "temporary" | "permanent";

export interface UserProfile {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  gender: Gender;
  address_type: AddressType;
  address: string;
  country_code: string;
  phone: string;
  country: string;
  state: string;
  city: string;
  has_password: boolean;
  created_at: string;
}

export interface SignUpPayload {
  first_name: string;
  last_name: string;
  gender: Gender;
  address_type: AddressType;
  address: string;
  country_code: string;
  phone: string;
  country: string;
  state: string;
  city: string;
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}
