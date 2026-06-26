/* ============================================================================
 * Ready-to-edit demo profiles, one per vertical. These seed the dashboard and
 * the simulator so anyone can test instantly, then edit the details in place.
 * ==========================================================================*/

import type { BusinessProfile, VerticalKey } from "./engine/types";

export const PRESETS: Record<VerticalKey, BusinessProfile> = {
  clinic: {
    type: "clinic", brand: "CityCare Clinic", agentName: "Aria", oneLiner: "a neighbourhood family clinic",
    days: "Mon–Sat", hours: "9 AM – 7 PM", languages: ["English", "Hindi", "Telugu"],
    slots: ["9 AM", "11 AM", "2 PM", "4 PM"], providers: ["Dr. Rao", "Dr. Iyer"],
    address: "Plot 5, Madhapur, Hyderabad",
    businessHours: { days: [1, 2, 3, 4, 5, 6], open: "09:00", close: "19:00" },
    services: [
      { name: "General Consultation", price: "₹500" },
      { name: "Specialist Consultation", price: "₹1,200" },
      { name: "Health Checkup", price: "₹3,500" },
    ],
    faqs: [
      { q: "Do you accept insurance?", a: "Yes, we accept most major health insurance providers — bring your card on the day." },
      { q: "Is parking available?", a: "Yes, free patient parking is available in the basement." },
    ],
  },
  dental: {
    type: "dental", brand: "BrightSmile Dental", agentName: "Aanya", oneLiner: "a family dental clinic",
    days: "Mon–Sat", hours: "10 AM – 8 PM", languages: ["English", "Hindi", "Telugu"],
    slots: ["10 AM", "12 PM", "3 PM", "5 PM"], providers: ["Dr. Shah", "Dr. Mehta"],
    address: "Road No.12, Banjara Hills, Hyderabad",
    businessHours: { days: [1, 2, 3, 4, 5, 6], open: "10:00", close: "20:00" },
    services: [
      { name: "Cleaning", price: "₹800" },
      { name: "Filling", price: "₹1,500" },
      { name: "Check-up", price: "Free" },
    ],
  },
  salon: {
    type: "salon", brand: "Lumière Studio", agentName: "Ria", oneLiner: "a hair & beauty studio",
    days: "Tue–Sun", hours: "11 AM – 8 PM", languages: ["English", "Hindi"],
    slots: ["11 AM", "1 PM", "4 PM", "6 PM"], providers: ["Sana", "Karan"],
    address: "Jubilee Hills, Hyderabad",
    businessHours: { days: [2, 3, 4, 5, 6, 0], open: "11:00", close: "20:00" },
    services: [
      { name: "Haircut", price: "₹600" },
      { name: "Hair Spa", price: "₹1,200" },
      { name: "Colour", price: "₹2,500" },
    ],
  },
  hotel: {
    type: "hotel", brand: "Kavaksh Retreat", agentName: "Maya", oneLiner: "a boutique wellness retreat",
    days: "Daily", hours: "24/7 front desk", languages: ["English", "Hindi"], slots: [],
    providers: ["Garden Room", "Lake View Suite", "Family Cottage"],
    address: "Off Srisailam Road, near Nagarjuna Sagar",
    services: [
      { name: "Garden Room", price: "₹4,500/night" },
      { name: "Lake View Suite", price: "₹7,000/night" },
    ],
  },
  restaurant: {
    type: "restaurant", brand: "Spice Route", agentName: "Dev", oneLiner: "a modern Indian kitchen",
    days: "Daily", hours: "12 PM – 11 PM", languages: ["English", "Hindi", "Telugu"],
    slots: ["12:30 PM", "1:30 PM", "7:30 PM", "9 PM"], providers: [],
    address: "Gachibowli, Hyderabad",
    businessHours: { days: [0, 1, 2, 3, 4, 5, 6], open: "12:00", close: "23:00" },
    services: [{ name: "Lunch", price: "" }, { name: "Dinner", price: "" }],
  },
  retail: {
    type: "retail", brand: "Riymay", agentName: "Noor", oneLiner: "a premium unisex clothing brand",
    days: "Mon–Sun", hours: "10 AM – 9 PM", languages: ["English", "Hindi", "Telugu"],
    slots: [], delivery: true, providers: [], address: "Hitech City, Hyderabad",
    services: [
      { name: "Oversized Tee", price: "₹2,000" },
      { name: "Cargo Pants", price: "₹3,200" },
      { name: "Hoodie", price: "₹3,800" },
    ],
  },
  travel: {
    type: "travel", brand: "Wander Co.", agentName: "Kai", oneLiner: "a curated tours & getaways company",
    days: "Mon–Sat", hours: "10 AM – 7 PM", languages: ["English", "Hindi"], slots: [], providers: [],
    address: "Online + Hyderabad office",
    services: [
      { name: "Goa Weekend (3D/2N)", price: "₹12,000 pp" },
      { name: "Manali Adventure (5D/4N)", price: "₹18,500 pp" },
      { name: "Kerala Backwaters (4D/3N)", price: "₹16,000 pp" },
    ],
  },
  fitness: {
    type: "fitness", brand: "Pulse Fitness", agentName: "Reya", oneLiner: "a boutique gym & studio",
    days: "Mon–Sun", hours: "6 AM – 10 PM", languages: ["English", "Hindi"],
    slots: ["7 AM", "9 AM", "6 PM", "8 PM"], providers: ["Coach Arjun", "Coach Leela"],
    address: "Kondapur, Hyderabad",
    businessHours: { days: [0, 1, 2, 3, 4, 5, 6], open: "06:00", close: "22:00" },
    services: [
      { name: "Strength Class", price: "₹400/session" },
      { name: "Yoga", price: "₹300/session" },
      { name: "Personal Training", price: "₹1,000/session" },
    ],
  },
  automotive: {
    type: "automotive", brand: "TorqueWorks", agentName: "Sam", oneLiner: "a multi-brand car service centre",
    days: "Mon–Sat", hours: "9 AM – 6 PM", languages: ["English", "Hindi", "Telugu"],
    slots: ["9 AM", "11 AM", "2 PM", "4 PM"], providers: [],
    address: "Kukatpally, Hyderabad",
    businessHours: { days: [1, 2, 3, 4, 5, 6], open: "09:00", close: "18:00" },
    services: [
      { name: "General Service", price: "₹3,000" },
      { name: "Wheel Alignment", price: "₹1,200" },
      { name: "AC Service", price: "₹2,500" },
    ],
  },
  generic: {
    type: "generic", brand: "Your Business", agentName: "Sam", oneLiner: "a local service business",
    days: "Mon–Fri", hours: "9 AM – 6 PM", languages: ["English"],
    slots: ["10 AM", "12 PM", "3 PM"], providers: [], address: "",
    businessHours: { days: [1, 2, 3, 4, 5], open: "09:00", close: "18:00" },
    services: [{ name: "Standard Booking", price: "" }],
  },
};
