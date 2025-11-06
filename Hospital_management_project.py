# hospital_management_project.py
"""
Hospital management script with both CLI and Streamlit UI.

Run the Streamlit UI with:

    streamlit run hospital_management_project.py

Or run the original CLI with:

    python hospital_management_project.py

This updated version adds:
- persistent patient storage in `patients_data.json` so patients survive page refreshes
- patient_id that increments from 1..n (persisted)
- discharge operation: when discharged the patient is marked discharged, their charges set to 0,
  and further operations for that patient are blocked
- 20 beds per bed type (ICU, Private, Semi-Private, General). Beds are tracked and only
  unused beds are shown in UI/CLI for assignment
- CLI and Streamlit UI share the same data file and logic

Additional: "View Patient Info" button that loads the patient's data into the sidebar
create form and into the edit fields (pre-filled, up-to-date).
"""

import os
import json
from pathlib import Path
try:
    import streamlit as st
except Exception:
    st = None

DATA_FILE = Path("patients_data.json")

BED_TYPES = {
    1: "ICU",
    2: "Private",
    3: "Semi-Private",
    4: "General",
}
BEDS_PER_TYPE = 20


class Doctor:
    def __init__(self, id, name, specialty, fee):
        self.id = id
        self.name = name
        self.specialty = specialty
        self.fee = float(fee)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "specialty": self.specialty, "fee": self.fee}

    @classmethod
    def from_dict(cls, d):
        return cls(d["id"], d["name"], d.get("specialty", ""), d.get("fee", 0.0))


DOCTORS = [
    Doctor(1, "Dr. A. Sharma", "General Medicine", 500.0),
    Doctor(2, "Dr. P. Rao", "Cardiology", 1500.0),
    Doctor(3, "Dr. L. Iyer", "Orthopedics", 1200.0),
    Doctor(4, "Dr. S. Kulkarni", "Pediatrics", 800.0),
]


class HospitalManagement:
    # patient_count persists by reading/writing DATA_FILE on start/changes.
    patient_count = 0

    def __init__(
        self,
        patient_id=None,
        room_charge=0.0,
        treatment_charge=0.0,
        pharmacy_charge=0.0,
        lab_charge=0.0,
        service_charge=500.0,
        name="",
        age=0,
        address="",
        admit_date="",
        discharge_date="",
        bed_id=None,  # e.g. 'ICU-1'
        discharged=False,
    ):
        # patient_id assigned externally or auto-increment
        if patient_id is None:
            HospitalManagement.patient_count += 1
            self.patient_id = HospitalManagement.patient_count
        else:
            self.patient_id = patient_id
            HospitalManagement.patient_count = max(HospitalManagement.patient_count, patient_id)

        self.room_charge = float(room_charge)
        self.treatment_charge = float(treatment_charge)
        self.pharmacy_charge = float(pharmacy_charge)
        self.lab_charge = float(lab_charge)
        self.service_charge = float(service_charge)
        self.name = name
        self.age = int(age)
        self.address = address
        self.admit_date = admit_date
        self.discharge_date = discharge_date
        self.bed_id = bed_id
        self.discharged = discharged

        # doctor
        self.assigned_doctor = None
        self.doctor_fee = 0.0

    # --- Serialization helpers ---
    def to_dict(self):
        return {
            "patient_id": self.patient_id,
            "room_charge": self.room_charge,
            "treatment_charge": self.treatment_charge,
            "pharmacy_charge": self.pharmacy_charge,
            "lab_charge": self.lab_charge,
            "service_charge": self.service_charge,
            "name": self.name,
            "age": self.age,
            "address": self.address,
            "admit_date": self.admit_date,
            "discharge_date": self.discharge_date,
            "bed_id": self.bed_id,
            "discharged": self.discharged,
            "assigned_doctor": self.assigned_doctor.to_dict() if self.assigned_doctor else None,
            "doctor_fee": self.doctor_fee,
        }

    @classmethod
    def from_dict(cls, d):
        inst = cls(
            patient_id=d.get("patient_id"),
            room_charge=d.get("room_charge", 0.0),
            treatment_charge=d.get("treatment_charge", 0.0),
            pharmacy_charge=d.get("pharmacy_charge", 0.0),
            lab_charge=d.get("lab_charge", 0.0),
            service_charge=d.get("service_charge", 500.0),
            name=d.get("name", ""),
            age=d.get("age", 0),
            address=d.get("address", ""),
            admit_date=d.get("admit_date", ""),
            discharge_date=d.get("discharge_date", ""),
            bed_id=d.get("bed_id"),
            discharged=d.get("discharged", False),
        )
        if d.get("assigned_doctor"):
            inst.assigned_doctor = Doctor.from_dict(d["assigned_doctor"])
            inst.doctor_fee = d.get("doctor_fee", 0.0)
        return inst

    # === Guard to block operations for discharged patient ===
    def _ensure_not_discharged(self):
        if self.discharged:
            raise RuntimeError("Operation not allowed: patient already discharged")

    # === Interactive CLI input ===
    def input_patient_data(self):
        if self.discharged:
            print("Cannot input data for a discharged patient")
            return
        self.name = input("Enter patient name:")
        try:
            self.age = int(input("Enter patient age:"))
        except Exception:
            self.age = 0
        self.address = input("Enter patient address:")
        self.admit_date = input("Enter admission date:")
        self.discharge_date = input("Enter expected discharge date")
        print("Assigned patient id:", self.patient_id)

    # === Bed selection helpers ===
    @staticmethod
    def _all_bed_ids_for_type(btype_index):
        tname = BED_TYPES[btype_index]
        return [f"{tname}-{i}" for i in range(1, BEDS_PER_TYPE + 1)]

    @staticmethod
    def compute_available_beds(patients_list):
        # patients_list: list of patient dicts
        used = set()
        for pd in patients_list:
            # if a patient has a bed and is not discharged -> bed is used
            if pd.get("bed_id") and not pd.get("discharged"):
                used.add(pd.get("bed_id"))
        available = {}
        for idx in BED_TYPES:
            all_ids = HospitalManagement._all_bed_ids_for_type(idx)
            available[BED_TYPES[idx]] = [b for b in all_ids if b not in used]
        return available

    # === Bed / room selection (CLI) ===
    def select_bed(self, patients_list):
        # patients_list is used to compute availability
        self._ensure_not_discharged()
        available = HospitalManagement.compute_available_beds(patients_list)
        print("We have the following bed types available (only unused beds shown):")
        for idx, name in BED_TYPES.items():
            print(f"{idx}. {name} -----> Rs {12000 if idx==1 else 8000 if idx==2 else 5000 if idx==3 else 3000} PN | Available: {len(available[name])}")
        try:
            choice = int(input("Enter your choice (1-4):"))
            if choice not in BED_TYPES:
                raise ValueError
        except Exception:
            print("Invalid input. Please enter numbers.")
            return
        # show actual available bed ids for chosen type
        tname = BED_TYPES[choice]
        if not available[tname]:
            print("No beds available of this type. Choose another type.")
            return
        print("Available beds:", available[tname])
        try:
            bed_choice = input("Enter bed id from the above list (e.g. ICU-1):")
            nights = int(input("For how many nights will the patient stay:"))
        except Exception:
            print("Invalid input.")
            return
        if bed_choice not in available[tname]:
            print("Invalid or already used bed id")
            return

        # set charging
        if choice == 1:
            self.room_charge = 12000 * nights
        elif choice == 2:
            self.room_charge = 8000 * nights
        elif choice == 3:
            self.room_charge = 5000 * nights
        elif choice == 4:
            self.room_charge = 3000 * nights
        self.bed_id = bed_choice
        print("Bed assigned:", self.bed_id)
        print("Room charges = Rs", self.room_charge, "\n")

    # === Treatments / procedures ===
    def treatment_menu(self):
        self._ensure_not_discharged()
        print("*****TREATMENT / PROCEDURE MENU*****")
        print("1. Consultation -----> Rs 500")
        print("2. Minor Procedure -> Rs 4000")
        print("3. Major Surgery ---> Rs 25000")
        print("4. Physiotherapy --> Rs 800 (per session)")
        print("5. ICU care extras -> Rs 5000")
        print("6. Exit")

        while True:
            try:
                c = int(input("Enter your choice:"))
            except Exception:
                print("Please enter a number")
                continue

            if c == 6:
                break

            if c in (1, 2, 3, 4, 5):
                try:
                    qty = int(input("Enter quantity / sessions (enter 1 if not applicable):"))
                except Exception:
                    qty = 1
                prices = {1: 500, 2: 4000, 3: 25000, 4: 800, 5: 5000}
                self.treatment_charge += prices[c] * qty
            else:
                print("Invalid option")

        print("Total Treatment Charges=Rs", self.treatment_charge, "\n")

    # === Pharmacy ===
    def pharmacy_bill(self):
        self._ensure_not_discharged()
        print("*****PHARMACY / MEDICINES MENU*****")
        print("1. Paracetamol 500mg -> Rs10", "2. Antibiotic (course) -> Rs400", "3. Painkiller -> Rs50", "4. Injection -> Rs150", "5. Medicine Kit -> Rs700", "6. Exit")
        while True:
            try:
                c = int(input("Enter your choice:"))
            except Exception:
                print("Please enter a number")
                continue

            if c == 6:
                break

            if c in (1, 2, 3, 4, 5):
                try:
                    qty = int(input("Enter the quantity:"))
                except Exception:
                    qty = 1
                prices = {1: 10, 2: 400, 3: 50, 4: 150, 5: 700}
                self.pharmacy_charge += prices[c] * qty
            else:
                print("Invalid option")

        print("Total Pharmacy Cost=Rs", self.pharmacy_charge, "\n")

    # === Lab tests ===
    def lab_tests(self):
        self._ensure_not_discharged()
        print("*****LAB TESTS MENU*****")
        print("1. Blood Test -> Rs 400", "2. X-Ray -> Rs 800", "3. MRI -> Rs 7000", "4. CT Scan -> Rs 5000", "5. Ultrasound -> Rs 1200", "6. Exit")

        while True:
            try:
                c = int(input("Enter your choice:"))
            except Exception:
                print("Please enter a number")
                continue

            if c == 6:
                break

            if c in (1, 2, 3, 4, 5):
                try:
                    qty = int(input("Enter quantity (or 1 if single test):"))
                except Exception:
                    qty = 1
                prices = {1: 400, 2: 800, 3: 7000, 4: 5000, 5: 1200}
                self.lab_charge += prices[c] * qty
            else:
                print("Invalid option")

        print("Total Lab Charges=Rs", self.lab_charge, "\n")

    # === Assign doctor (CLI / programmatic) ===
    def assign_doctor(self, doctor_id):
        self._ensure_not_discharged()
        for d in DOCTORS:
            if d.id == doctor_id:
                self.assigned_doctor = d
                self.doctor_fee = d.fee
                print(f"Assigned doctor: {d.name} ({d.specialty}) — Fee: Rs {d.fee}")
                return
        raise ValueError("Doctor with given id not found")

    def set_doctor(self, name, fee, specialty=""):
        self._ensure_not_discharged()
        self.assigned_doctor = Doctor(0, name, specialty, fee)
        self.doctor_fee = float(fee)

    # === Final bill display ===
    def display_bill(self):
        print("******HOSPITAL BILL******")
        print("Patient details:")
        print("Patient name:", self.name)
        print("Patient id:", self.patient_id)
        print("Age:", self.age)
        print("Patient address:", self.address)
        print("Admission date:", self.admit_date)
        print("Discharge date:", self.discharge_date)
        print("Bed id:", self.bed_id)
        print("Room charges:", self.room_charge)
        print("Treatment charges:", self.treatment_charge)
        print("Pharmacy charges:", self.pharmacy_charge)
        print("Lab charges:", self.lab_charge)

        # Doctor info
        if self.assigned_doctor:
            print(f"Assigned doctor: {self.assigned_doctor.name} ({self.assigned_doctor.specialty}) — Fee: Rs {self.doctor_fee}")
        else:
            print("Assigned doctor: None")

        subtotal = self.room_charge + self.treatment_charge + self.pharmacy_charge + self.lab_charge + self.doctor_fee
        print("Your sub total bill is:", subtotal)
        print("Additional Service Charges is", self.service_charge)
        print("Your grand total bill is:", subtotal + self.service_charge, "\n")

    # === Add items programmatically (used by Streamlit) ===
    def set_patient_data(self, name, age, address, admit_date, discharge_date):
        self._ensure_not_discharged()
        self.name = name
        self.age = int(age)
        self.address = address
        self.admit_date = admit_date
        self.discharge_date = discharge_date

    def set_bed_choice(self, bed_id, nights):
        self._ensure_not_discharged()
        # bed_id like 'ICU-1' -> determine type to choose charge rate
        if not bed_id:
            raise ValueError("bed_id required")
        tname = bed_id.split("-")[0]
        if tname == "ICU":
            rate = 12000
        elif tname == "Private":
            rate = 8000
        elif tname == "Semi-Private":
            rate = 5000
        elif tname == "General":
            rate = 3000
        else:
            raise ValueError("Unknown bed type")
        self.room_charge = rate * nights
        self.bed_id = bed_id

    def add_treatment_item(self, choice, qty):
        self._ensure_not_discharged()
        prices = {1: 500, 2: 4000, 3: 25000, 4: 800, 5: 5000}
        if choice in prices:
            self.treatment_charge += prices[choice] * qty
        else:
            raise ValueError("Invalid treatment choice")

    def add_pharmacy_item(self, choice, qty):
        self._ensure_not_discharged()
        prices = {1: 10, 2: 400, 3: 50, 4: 150, 5: 700}
        if choice in prices:
            self.pharmacy_charge += prices[choice] * qty
        else:
            raise ValueError("Invalid pharmacy choice")

    def add_lab_test(self, choice, qty):
        self._ensure_not_discharged()
        prices = {1: 400, 2: 800, 3: 7000, 4: 5000, 5: 1200}
        if choice in prices:
            self.lab_charge += prices[choice] * qty
        else:
            raise ValueError("Invalid lab test choice")

    def get_bill_text(self):
        lines = []
        lines.append("******SANJIVNI HOSPITAL BILL******")
        lines.append("Patient details:")
        lines.append(f"Patient id: {self.patient_id}")
        lines.append(f"Patient name: {self.name}")
        lines.append(f"Age: {self.age}")
        lines.append(f"Patient address: {self.address}")
        lines.append(f"Admission date: {self.admit_date}")
        lines.append(f"Discharge date: {self.discharge_date}")
        lines.append(f"Bed id: {self.bed_id}")
        lines.append(f"Room charges: {self.room_charge}")
        lines.append(f"Treatment charges: {self.treatment_charge}")
        lines.append(f"Pharmacy charges: {self.pharmacy_charge}")
        lines.append(f"Lab charges: {self.lab_charge}")
        if self.assigned_doctor:
            lines.append(f"Assigned doctor: {self.assigned_doctor.name} ({self.assigned_doctor.specialty})")
            lines.append(f"Doctor fee: {self.doctor_fee}")
        else:
            lines.append("Assigned doctor: None")
            lines.append("Doctor fee: 0.0")
        subtotal = self.room_charge + self.treatment_charge + self.pharmacy_charge + self.lab_charge + self.doctor_fee
        lines.append(f"Your sub total bill is: {subtotal}")
        lines.append(f"Additional Service Charges is {self.service_charge}")
        lines.append(f"====================================")
        lines.append(f"Your grandtotal bill is: {subtotal + self.service_charge}")
        return "\n".join(lines)

    # === Discharge patient ===
    def discharge(self, discharge_date=None, zero_out_charges=True):
        # Mark patient discharged, optionally zero out charges and free bed
        if self.discharged:
            print("Patient already discharged")
            return
        self.discharged = True
        if discharge_date:
            self.discharge_date = discharge_date
        if zero_out_charges:
            # For the user's request, make amounts zero upon discharge
            self.room_charge = 0.0
            self.treatment_charge = 0.0
            self.pharmacy_charge = 0.0
            self.lab_charge = 0.0
            self.doctor_fee = 0.0
        print(f"Patient {self.patient_id} discharged. Bed {self.bed_id} is now free.")
        # free bed happens implicitly because availability is computed by checking discharged flag


# === Persistence helpers ===

def load_data():
    if not DATA_FILE.exists():
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
        return items
    except Exception:
        return []


def save_data(patients_list):
    # patients_list: list of HospitalManagement or dicts
    to_save = []
    for p in patients_list:
        if isinstance(p, HospitalManagement):
            to_save.append(p.to_dict())
        else:
            to_save.append(p)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2)


# === CLI main ===

def main():
    raw = load_data()
    # convert raw dicts to objects
    patients = [HospitalManagement.from_dict(d) for d in raw]
    current = None

    while True:
        print("\n1.Enter Patient Data")
        print("2.Select bed / calculate bed charges")
        print("3.Add treatment / procedure charges")
        print("4.Add pharmacy charges")
        print("5.Add lab tests")
        print("6.Show total bill")
        print("7.Patients (persisted)")
        print("8.List doctors")
        print("9.Assign doctor to current patient")
        print("10.Discharge current patient")
        print("11.Save & Exit")

        try:
            b = int(input("enter your choice:"))
        except Exception:
            print("Please enter a number from the menu")
            continue

        if b == 1:
            current = HospitalManagement()
            current.input_patient_data()
            patients.append(current)
            save_data(patients)
            print(f"Patient created with id {current.patient_id}")
        elif b == 2:
            if current:
                current.select_bed([p.to_dict() for p in patients])
                save_data(patients)
            else:
                print("please enter Patient data first")
        elif b == 3:
            if current:
                try:
                    current.treatment_menu()
                    save_data(patients)
                except RuntimeError as e:
                    print(e)
            else:
                print("please enter Patient data first")
        elif b == 4:
            if current:
                try:
                    current.pharmacy_bill()
                    save_data(patients)
                except RuntimeError as e:
                    print(e)
            else:
                print("please enter Patient data first")
        elif b == 5:
            if current:
                try:
                    current.lab_tests()
                    save_data(patients)
                except RuntimeError as e:
                    print(e)
            else:
                print("please enter Patient data first")
        elif b == 6:
            if current:
                current.display_bill()
            else:
                print("please enter Patient data first")
        elif b == 7:
            # show persisted patients summary
            for p in patients:
                print(p.to_dict())
        elif b == 8:
            for d in DOCTORS:
                print(f"{d.id}. {d.name} — {d.specialty} — Fee: Rs {d.fee}")
        elif b == 9:
            if not current:
                print("please enter Patient data first")
                continue
            try:
                did = int(input("Enter doctor id to assign (use option 8 to list doctors):"))
                current.assign_doctor(did)
                save_data(patients)
            except Exception as e:
                print("Error assigning doctor:", e)
        elif b == 10:
            if not current:
                print("please enter Patient data first")
                continue
            ddate = input("Enter discharge date (leave empty for today):")
            current.discharge(discharge_date=ddate or None)
            save_data(patients)
        elif b == 11:
            save_data(patients)
            print("Saved. Exiting.")
            quit()
        else:
            print("Choose a valid menu option")


# === Streamlit app ===

def streamlit_app():
    st.title("ABC Hospital — Patient Admission & Billing (persistent)")

    # Load persisted patients into session state once
    if "patients" not in st.session_state:
        raw = load_data()
        st.session_state.patients = [HospitalManagement.from_dict(d) for d in raw]

    # --- Initialize sidebar widget keys (so we can programmatically set them) ---
    # Only set defaults if the keys don't exist
    sidebar_defaults = {
        "create_name": "",
        "create_age": 30,
        "create_address": "",
        "create_admit_date": "",
        "create_discharge_date": "",
        "create_bed_type": list(BED_TYPES.values())[0],
        "create_bed_choice": None,
        "create_nights": 1,
    }
    for k, v in sidebar_defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # recompute available beds
    available_beds = HospitalManagement.compute_available_beds([p.to_dict() for p in st.session_state.patients])

    st.sidebar.header("Create / Load patient")
    # Create new patient (widgets now have explicit keys so they can be set programmatically)
    name = st.sidebar.text_input("Name", value=st.session_state.get("create_name", ""), key="create_name")
    age = st.sidebar.number_input("Age", min_value=0, value=int(st.session_state.get("create_age", 30)), key="create_age")
    address = st.sidebar.text_area("Address", value=st.session_state.get("create_address", ""), key="create_address")
    admit_date = st.sidebar.text_input("Admission date", value=st.session_state.get("create_admit_date", ""), key="create_admit_date")
    discharge_date = st.sidebar.text_input("Expected discharge date", value=st.session_state.get("create_discharge_date", ""), key="create_discharge_date")

    # Bed type and bed selection should show only unused beds but if a patient bed is being loaded, ensure it's included
    bed_type_list = [BED_TYPES[i] for i in sorted(BED_TYPES.keys())]
    bed_type = st.sidebar.selectbox("Bed type", bed_type_list, index=bed_type_list.index(st.session_state.get("create_bed_type", bed_type_list[0])), key="create_bed_type")

    # compute beds_for_type and ensure any existing session_state create_bed_choice is included
    beds_for_type = available_beds.get(bed_type, []).copy()
    cur_choice = st.session_state.get("create_bed_choice")
    if cur_choice and cur_choice not in beds_for_type:
        # include the existing bed (so we can view/edit a patient who already occupies a bed)
        beds_for_type = [cur_choice] + beds_for_type

    if beds_for_type:
        bed_choice = st.sidebar.selectbox("Choose available bed", beds_for_type, index=0 if st.session_state.get("create_bed_choice") is None else (0 if beds_for_type[0] == st.session_state.get("create_bed_choice") else 0), key="create_bed_choice")
    else:
        st.sidebar.write("No beds available for this type")
        bed_choice = None

    nights = st.sidebar.number_input("Nights", min_value=1, value=int(st.session_state.get("create_nights", 1)), key="create_nights")

    if st.sidebar.button("Create Patient"):
        # create and assign bed
        if bed_choice is None:
            st.sidebar.error("No available bed selected for chosen type")
        else:
            inst = HospitalManagement()
            inst.set_patient_data(name, int(age), address, admit_date, discharge_date)
            try:
                inst.set_bed_choice(bed_choice, int(nights))
            except Exception as e:
                st.sidebar.error(f"Error setting bed: {e}")
                return
            st.session_state.patients.append(inst)
            save_data(st.session_state.patients)
            st.sidebar.success(f"Patient created — id: {inst.patient_id} — Bed: {inst.bed_id}")
            # update available_beds to remove assigned bed in this run
            available_beds = HospitalManagement.compute_available_beds([p.to_dict() for p in st.session_state.patients])

    st.header("Select patient to operate on")
    # Show list of patients including discharged ones. But operations disabled for discharged ones.
    patient_options = [f"{p.patient_id}: {p.name or '(no name)'} - {p.bed_id or 'No bed'} - {'DISCHARGED' if p.discharged else 'ADMITTED'}" for p in st.session_state.patients]
    if patient_options:
        selected = st.selectbox("Choose patient", ["None"] + patient_options)
    else:
        selected = "None"

    def get_selected_inst():
        if selected == "None":
            return None
        pid = int(selected.split(":")[0])
        for p in st.session_state.patients:
            if p.patient_id == pid:
                return p
        return None

    inst = get_selected_inst()

    if inst:
        st.subheader(f"Patient {inst.patient_id} — {inst.name}")
        st.write(inst.get_bill_text())

        # NEW: View Patient Info button — populates sidebar and edit fields with current patient data
        if st.button("View Patient Info"):
            # populate create/sidebar fields
            st.session_state["create_name"] = inst.name or ""
            st.session_state["create_age"] = int(inst.age or 0)
            st.session_state["create_address"] = inst.address or ""
            st.session_state["create_admit_date"] = inst.admit_date or ""
            st.session_state["create_discharge_date"] = inst.discharge_date or ""
            # set bed type and bed choice so sidebar shows patient's bed (even if occupied)
            if inst.bed_id:
                st.session_state["create_bed_type"] = inst.bed_id.split("-")[0]
                st.session_state["create_bed_choice"] = inst.bed_id
            else:
                st.session_state["create_bed_choice"] = None
            st.session_state["create_nights"] = 1

            # populate editing UI fields (so "Update Bill" panel is prefilled and visible)
            st.session_state[f"editing_{inst.patient_id}"] = True
            # set edit field keys so values appear inside the "Edit patient bill" UI
            st.session_state[f"edit_name_{inst.patient_id}"] = inst.name or ""
            st.session_state[f"edit_age_{inst.patient_id}"] = int(inst.age or 0)
            st.session_state[f"edit_address_{inst.patient_id}"] = inst.address or ""
            st.session_state[f"edit_admit_{inst.patient_id}"] = inst.admit_date or ""
            st.session_state[f"edit_discharge_{inst.patient_id}"] = inst.discharge_date or ""
            st.session_state[f"edit_bed_{inst.patient_id}"] = inst.bed_id or ""
            st.session_state[f"edit_room_{inst.patient_id}"] = float(inst.room_charge or 0.0)
            st.session_state[f"edit_treat_{inst.patient_id}"] = float(inst.treatment_charge or 0.0)
            st.session_state[f"edit_pharm_{inst.patient_id}"] = float(inst.pharmacy_charge or 0.0)
            st.session_state[f"edit_lab_{inst.patient_id}"] = float(inst.lab_charge or 0.0)
            st.session_state[f"edit_service_{inst.patient_id}"] = float(inst.service_charge or 0.0)
            # doctor related keys
            # If assigned preset doctor, set selectbox to that; otherwise fill custom fields
            if inst.assigned_doctor and inst.assigned_doctor.id != 0:
                # find index text for selectbox: "id. Name — Specialty — Rs fee"
                sel_text = f"{inst.assigned_doctor.id}. {inst.assigned_doctor.name} — {inst.assigned_doctor.specialty} — Rs {inst.assigned_doctor.fee}"
                st.session_state[f"edit_docsel_{inst.patient_id}"] = sel_text
                st.session_state[f"edit_custdoc_{inst.patient_id}"] = ""
                st.session_state[f"edit_custspec_{inst.patient_id}"] = ""
                st.session_state[f"edit_custfee_{inst.patient_id}"] = float(inst.doctor_fee or 0.0)
            elif inst.assigned_doctor and inst.assigned_doctor.id == 0:
                st.session_state[f"edit_docsel_{inst.patient_id}"] = "None"
                st.session_state[f"edit_custdoc_{inst.patient_id}"] = inst.assigned_doctor.name
                st.session_state[f"edit_custspec_{inst.patient_id}"] = inst.assigned_doctor.specialty
                st.session_state[f"edit_custfee_{inst.patient_id}"] = float(inst.doctor_fee or 0.0)
            else:
                st.session_state[f"edit_docsel_{inst.patient_id}"] = "None"
                st.session_state[f"edit_custdoc_{inst.patient_id}"] = ""
                st.session_state[f"edit_custspec_{inst.patient_id}"] = ""
                st.session_state[f"edit_custfee_{inst.patient_id}"] = 0.0

            # rerun so sidebar & edit fields update instantly
            st.experimental_rerun()

        if inst.discharged:
            st.warning("This patient is discharged. Further operations are disabled.")
        else:
            st.write("--- Operations (disabled once patient is discharged) ---")

            # Treatments
            st.write("Treatments / Procedures")
            col1, col2 = st.columns(2)
            with col1:
                t1 = st.number_input("Consultations (Rs500)", min_value=0, value=0, key=f"t1_{inst.patient_id}")
                t2 = st.number_input("Minor Procedures (Rs4000)", min_value=0, value=0, key=f"t2_{inst.patient_id}")
                t3 = st.number_input("Major Surgery (Rs25000)", min_value=0, value=0, key=f"t3_{inst.patient_id}")
            with col2:
                t4 = st.number_input("Physio sessions (Rs800)", min_value=0, value=0, key=f"t4_{inst.patient_id}")
                t5 = st.number_input("ICU extras (Rs5000)", min_value=0, value=0, key=f"t5_{inst.patient_id}")

            if st.button("Add Treatments"):
                try:
                    for idx, qty in enumerate((t1, t2, t3, t4, t5), start=1):
                        if qty:
                            inst.add_treatment_item(idx, int(qty))
                    save_data(st.session_state.patients)
                    st.success(f"Added treatments. Total treatment cost: Rs {inst.treatment_charge}")
                except RuntimeError as e:
                    st.error(str(e))

            # Pharmacy
            st.write("Pharmacy")
            p1 = st.number_input("Paracetamol (Rs10)", min_value=0, value=0, key=f"p1_{inst.patient_id}")
            p2 = st.number_input("Antibiotic course (Rs400)", min_value=0, value=0, key=f"p2_{inst.patient_id}")
            p3 = st.number_input("Painkiller (Rs50)", min_value=0, value=0, key=f"p3_{inst.patient_id}")
            p4 = st.number_input("Injection (Rs150)", min_value=0, value=0, key=f"p4_{inst.patient_id}")
            p5 = st.number_input("Medicine Kit (Rs700)", min_value=0, value=0, key=f"p5_{inst.patient_id}")
            if st.button("Add Pharmacy Items"):
                try:
                    for idx, qty in enumerate((p1, p2, p3, p4, p5), start=1):
                        if qty:
                            inst.add_pharmacy_item(idx, int(qty))
                    save_data(st.session_state.patients)
                    st.success(f"Added medicines. Total pharmacy cost: Rs {inst.pharmacy_charge}")
                except RuntimeError as e:
                    st.error(str(e))

            # Lab
            st.write("Lab Tests")
            l1 = st.number_input("Blood Test (Rs400)", min_value=0, value=0, key=f"l1_{inst.patient_id}")
            l2 = st.number_input("X-Ray (Rs800)", min_value=0, value=0, key=f"l2_{inst.patient_id}")
            l3 = st.number_input("MRI (Rs7000)", min_value=0, value=0, key=f"l3_{inst.patient_id}")
            l4 = st.number_input("CT Scan (Rs5000)", min_value=0, value=0, key=f"l4_{inst.patient_id}")
            l5 = st.number_input("Ultrasound (Rs1200)", min_value=0, value=0, key=f"l5_{inst.patient_id}")
            if st.button("Add Lab Tests"):
                try:
                    for idx, qty in enumerate((l1, l2, l3, l4, l5), start=1):
                        if qty:
                            inst.add_lab_test(idx, int(qty))
                    save_data(st.session_state.patients)
                    st.success(f"Added lab tests. Total lab cost: Rs {inst.lab_charge}")
                except RuntimeError as e:
                    st.error(str(e))

            # Doctor assignment
            st.write("Doctor assignment")
            doctor_names = [f"{d.id}. {d.name} — {d.specialty} — Rs {d.fee}" for d in DOCTORS]
            selected_doctor = st.selectbox("Choose doctor to assign (or choose 'None')", ["None"] + doctor_names, key=f"docsel_{inst.patient_id}")
            custom_name = st.text_input("Or enter custom doctor name (optional)", key=f"custdoc_{inst.patient_id}")
            custom_specialty = st.text_input("Custom doctor specialty (optional)", key=f"custspec_{inst.patient_id}")
            custom_fee = st.number_input("Custom doctor fee (if custom doctor)", min_value=0.0, value=0.0, key=f"custfee_{inst.patient_id}")

            if st.button("Assign doctor"):
                try:
                    if selected_doctor and selected_doctor != "None":
                        did = int(selected_doctor.split(".")[0])
                        inst.assign_doctor(did)
                        save_data(st.session_state.patients)
                        st.success(f"Assigned {inst.assigned_doctor.name} — Fee: Rs {inst.doctor_fee}")
                    elif custom_name:
                        inst.set_doctor(custom_name, float(custom_fee), custom_specialty)
                        save_data(st.session_state.patients)
                        st.success(f"Assigned custom doctor {custom_name} — Fee: Rs {inst.doctor_fee}")
                    else:
                        st.info("No doctor assigned")
                except RuntimeError as e:
                    st.error(str(e))

            # Calculate bed charges (change nights / bed)
            st.write("Bed / Room charge adjustments")
            new_bed_type = st.selectbox("Change bed type (only unused beds shown)", ["(no change)"] + [BED_TYPES[i] for i in sorted(BED_TYPES.keys())], key=f"bedtypechg_{inst.patient_id}")
            if new_bed_type and new_bed_type != "(no change)":
                beds_for_type = HospitalManagement.compute_available_beds([p.to_dict() for p in st.session_state.patients]).get(new_bed_type, [])
                if beds_for_type:
                    new_bed_choice = st.selectbox("Pick new bed (unused)", beds_for_type, key=f"bedpick_{inst.patient_id}")
                else:
                    new_bed_choice = None
                new_nights = st.number_input("Nights for new bed", min_value=1, value=1, key=f"newnights_{inst.patient_id}")
                if st.button("Change bed and recalc charges") and new_bed_choice:
                    try:
                        inst.set_bed_choice(new_bed_choice, int(new_nights))
                        save_data(st.session_state.patients)
                        st.success(f"Bed changed to {inst.bed_id}. Room charge now Rs {inst.room_charge}")
                    except RuntimeError as e:
                        st.error(str(e))

            # Show bill and discharge
            if st.button("Show Bill"):
                st.text_area("Bill", value=inst.get_bill_text(), height=300)

            # NEW: Update Bill button (loads all editable fields for the patient)
            if st.button("Update Bill"):
                # mark editing flag in session state so fields persist
                st.session_state[f"editing_{inst.patient_id}"] = True

            if st.session_state.get(f"editing_{inst.patient_id}"):
                st.write("--- Edit patient bill (modify values and click Save Updates) ---")
                # prefilled editable fields (we rely on session_state keys populated either by View Patient Info or Save Updates)
                edit_name = st.text_input("Name", value=st.session_state.get(f"edit_name_{inst.patient_id}", inst.name), key=f"edit_name_{inst.patient_id}")
                edit_age = st.number_input("Age", min_value=0, value=int(st.session_state.get(f"edit_age_{inst.patient_id}", inst.age or 0)), key=f"edit_age_{inst.patient_id}")
                edit_address = st.text_area("Address", value=st.session_state.get(f"edit_address_{inst.patient_id}", inst.address or ""), key=f"edit_address_{inst.patient_id}")
                edit_admit = st.text_input("Admission date", value=st.session_state.get(f"edit_admit_{inst.patient_id}", inst.admit_date or ""), key=f"edit_admit_{inst.patient_id}")
                edit_discharge = st.text_input("Discharge date", value=st.session_state.get(f"edit_discharge_{inst.patient_id}", inst.discharge_date or ""), key=f"edit_discharge_{inst.patient_id}")
                edit_bed = st.text_input("Bed id (e.g. ICU-1)", value=st.session_state.get(f"edit_bed_{inst.patient_id}", inst.bed_id or ""), key=f"edit_bed_{inst.patient_id}")

                st.write("Charges (edit numeric fields as needed)")
                edit_room = st.number_input("Room charge", min_value=0.0, value=float(st.session_state.get(f"edit_room_{inst.patient_id}", inst.room_charge or 0.0)), key=f"edit_room_{inst.patient_id}")
                edit_treatment = st.number_input("Treatment charge", min_value=0.0, value=float(st.session_state.get(f"edit_treat_{inst.patient_id}", inst.treatment_charge or 0.0)), key=f"edit_treat_{inst.patient_id}")
                edit_pharmacy = st.number_input("Pharmacy charge", min_value=0.0, value=float(st.session_state.get(f"edit_pharm_{inst.patient_id}", inst.pharmacy_charge or 0.0)), key=f"edit_pharm_{inst.patient_id}")
                edit_lab = st.number_input("Lab charge", min_value=0.0, value=float(st.session_state.get(f"edit_lab_{inst.patient_id}", inst.lab_charge or 0.0)), key=f"edit_lab_{inst.patient_id}")
                edit_service = st.number_input("Service charge", min_value=0.0, value=float(st.session_state.get(f"edit_service_{inst.patient_id}", inst.service_charge or 0.0)), key=f"edit_service_{inst.patient_id}")

                st.write("Doctor (choose existing or enter custom)")
                edit_doc_select = st.selectbox("Choose doctor", ["None"] + doctor_names, index=0, key=f"edit_docsel_{inst.patient_id}")
                edit_cust_doc = st.text_input("Custom doctor name (optional)", value=st.session_state.get(f"edit_custdoc_{inst.patient_id}", (inst.assigned_doctor.name if inst.assigned_doctor and inst.assigned_doctor.id == 0 else "")), key=f"edit_custdoc_{inst.patient_id}")
                edit_cust_spec = st.text_input("Custom doctor specialty (optional)", value=st.session_state.get(f"edit_custspec_{inst.patient_id}", (inst.assigned_doctor.specialty if inst.assigned_doctor and inst.assigned_doctor.id == 0 else "")), key=f"edit_custspec_{inst.patient_id}")
                edit_cust_fee = st.number_input("Custom doctor fee (if custom)", min_value=0.0, value=float(st.session_state.get(f"edit_custfee_{inst.patient_id}", inst.doctor_fee or 0.0)), key=f"edit_custfee_{inst.patient_id}")

                if st.button("Save Updates"):
                    try:
                        # assign edited values back to instance
                        inst.name = edit_name
                        inst.age = int(edit_age)
                        inst.address = edit_address
                        inst.admit_date = edit_admit
                        inst.discharge_date = edit_discharge
                        inst.bed_id = edit_bed or None

                        inst.room_charge = float(edit_room)
                        inst.treatment_charge = float(edit_treatment)
                        inst.pharmacy_charge = float(edit_pharmacy)
                        inst.lab_charge = float(edit_lab)
                        inst.service_charge = float(edit_service)

                        # doctor assignment logic: if selected a preset doctor, assign; else if custom provided, set custom.
                        if edit_doc_select and edit_doc_select != "None":
                            did = int(edit_doc_select.split(".")[0])
                            # assign using assign_doctor which has discharge guard (we are in non-discharged branch)
                            inst.assign_doctor(did)
                        elif edit_cust_doc:
                            inst.set_doctor(edit_cust_doc, float(edit_cust_fee), edit_cust_spec)
                        else:
                            # clear doctor if none chosen and no custom provided
                            inst.assigned_doctor = None
                            inst.doctor_fee = 0.0

                        save_data(st.session_state.patients)
                        st.success("Patient bill updated and saved.")
                        # turn off editing flag
                        st.session_state[f"editing_{inst.patient_id}"] = False
                    except RuntimeError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"Error saving updates: {e}")

            if st.button("Discharge Patient"):
                # perform discharge, zero amounts and free bed
                discharge_input_key = f"discharge_input_{inst.patient_id}"
                # show a small text input inline for discharge date to choose before discharging
                ddate = st.text_input(f"Discharge date for {inst.patient_id} (leave empty for today)", value="", key=discharge_input_key)
                # call discharge only after user confirms (clicks a separate confirm button)
                if st.button("Confirm Discharge"):
                    inst.discharge(discharge_date=ddate or None)
                    save_data(st.session_state.patients)
                    st.success("Patient discharged. All future operations for this patient are disabled and charges set to 0")

    else:
        st.info("No patient selected")

    st.header("All patients (persisted)")
    # List persisted patients with basic info
    if st.button("Reload from disk"):
        raw = load_data()
        st.session_state.patients = [HospitalManagement.from_dict(d) for d in raw]
        st.experimental_rerun()

    if st.session_state.patients:
        for p in st.session_state.patients:
            st.write(p.to_dict())
    else:
        st.write("No patients found")


if __name__ == "__main__":
    # If running under Streamlit (streamlit run ...), Streamlit sets the
    # environment variable STREAMLIT_RUN_MAIN during the main run.
    if st is not None and os.environ.get("STREAMLIT_RUN_MAIN"):
        streamlit_app()
    else:
        main()
