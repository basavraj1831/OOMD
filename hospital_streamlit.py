"""
Streamlit UI for the Hospital Management System
with Doctor assignment, Discharge, and ₹0 bill after discharge.

Run this file with:

    streamlit run streamlit_run_this_file.py
"""

import streamlit as st
from datetime import datetime

from Hospital_management_project import (
    HospitalManagement,
    DOCTORS,
    load_data,
    save_data,
    BED_TYPES,
)


def main():
    st.set_page_config(page_title="🏥 Sanjivni Hospital Management", layout="wide")
    st.markdown(
        """
        <h1 style="
            margin-bottom: 30px;
            text-align: center;
            items-align: center;
            font-size: 50px;
            font-family: Arial, sans-serif;
        ">
            <span style='color:#ff4d4d;'>Sanjivni</span> Hospital
        </h1>
        """,
        unsafe_allow_html=True,
    )

    # -------- Load persisted patient data --------
    if "patients" not in st.session_state:
        raw = load_data()
        st.session_state.patients = [HospitalManagement.from_dict(d) for d in raw]

    if "inst" not in st.session_state:
        st.session_state.inst = None

    # -------- Sidebar inputs --------
    st.sidebar.header("🧍Patient Information : ")

    defaults = {
        "sidebar_name": "",
        "sidebar_age": 30,
        "sidebar_address": "",
        "sidebar_admit": "",
        "sidebar_nights": 1,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    name = st.sidebar.text_input("Full Name", value=st.session_state.sidebar_name)
    age = st.sidebar.number_input("Age", min_value=0, value=st.session_state.sidebar_age)
    address = st.sidebar.text_area("Address", value=st.session_state.sidebar_address)
    admit_date = st.sidebar.text_input(
        "Admission Date (YYYY-MM-DD)",
        value=st.session_state.sidebar_admit or datetime.today().strftime("%Y-%m-%d"),
    )

    # Automatically calculate nights based on admission date
    try:
        if admit_date:
            admit_dt = datetime.strptime(admit_date, "%Y-%m-%d").date()
            today = datetime.today().date()
            nights = max((today - admit_dt).days, 1)  # At least 1 night
        else:
            nights = 1
    except ValueError:
        nights = 1

    # -------- Create or Update Patient --------
    if st.sidebar.button("💾 Create Patient"):
        if not name:
            st.sidebar.error("⚠️ Please enter a patient name.")
        else:
            if st.session_state.inst is None:
                inst = HospitalManagement()
                inst.set_patient_data(name, int(age), address, admit_date, "")
                st.session_state.patients.append(inst)
                st.session_state.inst = inst
                save_data(st.session_state.patients)
                st.sidebar.success(f"✅ Created Patient — ID: {inst.patient_id}")
            else:
                inst = st.session_state.inst
                inst.set_patient_data(name, int(age), address, admit_date, "")
                save_data(st.session_state.patients)
                st.sidebar.success(f"✅ Updated Patient {inst.patient_id}")

    # -------- Bed Selection (main page) --------

    st.subheader("🛏️ Bed Selection :")

    available_beds = HospitalManagement.compute_available_beds([p.to_dict() for p in st.session_state.patients])
    bed_type = st.selectbox("Select Bed Type", [BED_TYPES[i] for i in sorted(BED_TYPES.keys())], index=0)

    beds_for_type = available_beds.get(bed_type, []).copy()
    if st.session_state.inst and st.session_state.inst.bed_id:
        inst_bed = st.session_state.inst.bed_id
        if inst_bed.startswith(bed_type) and inst_bed not in beds_for_type:
            beds_for_type.insert(0, inst_bed)

    bed_choice = st.selectbox("Choose Bed", beds_for_type or ["No beds available"])

    if st.button("🛏️ Assign Bed"):
        inst = st.session_state.inst
        if not inst:
            st.warning("⚠️ Create or load a patient first.")
        elif bed_choice == "No beds available":
            st.warning("⚠️ No bed available for this type.")
        else:
            st.session_state.inst.set_bed_choice(bed_choice, nights)
            save_data(st.session_state.patients)
            st.success(f"✅ Assigned Bed {bed_choice} to patient {st.session_state.inst.patient_id}")

    # -------- Doctor Assignment --------
    st.markdown("<hr style='border: 1px solid white'>", unsafe_allow_html=True)

    st.subheader("👨‍⚕️ Doctor Assignment :")

    doctor_names = [f"{d.name} ({d.specialty}) — ₹{d.fee}" for d in DOCTORS]
    doctor_display = ["(none)"] + doctor_names

    default_doc_index = 0
    if st.session_state.inst and st.session_state.inst.assigned_doctor:
        doc_str = f"{st.session_state.inst.assigned_doctor.name} ({st.session_state.inst.assigned_doctor.specialty}) — ₹{st.session_state.inst.assigned_doctor.fee}"
        if doc_str in doctor_names:
            default_doc_index = doctor_names.index(doc_str) + 1

    selected_doc = st.selectbox("Select Doctor", doctor_display, index=default_doc_index)

    if st.button("🩺 Assign Doctor"):
        inst = st.session_state.inst
        if not inst:
            st.warning("⚠️ Create or load a patient first.")
        elif selected_doc == "(none)":
            st.warning("⚠️ Select a valid doctor.")
        else:
            doc_index = doctor_names.index(selected_doc)
            inst.assign_doctor(DOCTORS[doc_index].id)
            save_data(st.session_state.patients)
            st.success(f"✅ Assigned {DOCTORS[doc_index].name} to patient {inst.patient_id}")

    # -------- Treatments (two columns, persistent) --------
    st.markdown("<hr style='border: 1px solid white'>", unsafe_allow_html=True)
    st.subheader("💉 Treatments / Procedures :")
    col1, col2 = st.columns(2)

    inst = st.session_state.inst
    patient_suffix = f"_{inst.patient_id}" if inst else ""

    # Initialize treatment_items dict if not exists
    if inst and not hasattr(inst, "treatment_items"):
        inst.treatment_items = {}

    # Map of treatments
    treatment_map = {
        1: ("Consultations", 500),
        2: ("Minor Procedures", 4000),
        3: ("Major Surgeries", 25000),
        4: ("Physio Sessions", 800),
        5: ("ICU Care", 5000),
    }

    # Get existing quantities
    existing_treatments = {name: inst.treatment_items.get(name, 0) for name, _ in treatment_map.values()} if inst else {}

    # Input fields showing saved quantities
    t1 = col1.number_input("Consultations (₹500)", min_value=0, value=existing_treatments.get("Consultations", 0), key=f"t1_add{patient_suffix}")
    t2 = col1.number_input("Minor Procedures (₹4000)", min_value=0, value=existing_treatments.get("Minor Procedures", 0), key=f"t2_add{patient_suffix}")
    t3 = col1.number_input("Major Surgeries (₹25000)", min_value=0, value=existing_treatments.get("Major Surgeries", 0), key=f"t3_add{patient_suffix}")
    t4 = col2.number_input("Physio Sessions (₹800)", min_value=0, value=existing_treatments.get("Physio Sessions", 0), key=f"t4_add{patient_suffix}")
    t5 = col2.number_input("ICU Care (₹5000)", min_value=0, value=existing_treatments.get("ICU Care", 0), key=f"t5_add{patient_suffix}")

    # Button to update treatments
    if st.button("➕ Add Treatments"):
        if not inst:
            st.warning("⚠️ Create or load a patient first.")
        elif inst.discharged:
            st.warning("⚠️ Cannot add treatments after discharge.")
        else:
            for idx, qty in enumerate((t1, t2, t3, t4, t5), start=1):
                name, price = treatment_map[idx]
                inst.treatment_items[name] = int(qty)

            # Update total treatment charge
            inst.treatment_charge = sum(
                inst.treatment_items[name] * price for name, price in [v for v in treatment_map.values()]
            )

            save_data(st.session_state.patients)
            st.success(f"✅ Treatments updated | Total: ₹{inst.treatment_charge}")

    # -------- Pharmacy (two columns) --------
    st.markdown("<hr style='border: 1px solid white'>", unsafe_allow_html=True)

    st.subheader("💊 Pharmacy Items :")
    col1, col2 = st.columns(2)

    inst = st.session_state.get("inst")

    # Get a unique key suffix per patient
    patient_suffix = f"_{inst.patient_id}" if inst else ""

    # Initialize pharmacy_items dict if not exists
    if inst and not hasattr(inst, "pharmacy_items"):
        inst.pharmacy_items = {}

    # Map of medicines
    pharmacy_map = {
        1: ("Paracetamol", 10),
        2: ("Antibiotic Course", 400),
        3: ("Painkiller", 50),
        4: ("Injection", 150),
        5: ("Medicine Kit", 700),
    }

    # Get existing quantities (defaults to 0 if not set)
    existing_quantities = {name: inst.pharmacy_items.get(name, 0) for name, _ in pharmacy_map.values()} if inst else {}

    # Input fields with default = stored quantity
    p1 = col1.number_input("Paracetamol (₹10)", min_value=0, value=existing_quantities.get("Paracetamol", 0), key=f"p1_add{patient_suffix}")
    p2 = col1.number_input("Antibiotic Course (₹400)", min_value=0, value=existing_quantities.get("Antibiotic Course", 0), key=f"p2_add{patient_suffix}")
    p3 = col1.number_input("Painkiller (₹50)", min_value=0, value=existing_quantities.get("Painkiller", 0), key=f"p3_add{patient_suffix}")
    p4 = col2.number_input("Injection (₹150)", min_value=0, value=existing_quantities.get("Injection", 0), key=f"p4_add{patient_suffix}")
    p5 = col2.number_input("Medicine Kit (₹700)", min_value=0, value=existing_quantities.get("Medicine Kit", 0), key=f"p5_add{patient_suffix}")

    # Button to add/update pharmacy items
    if st.button("➕ Add Pharmacy"):
        if not inst:
            st.warning("⚠️ Create or load a patient first.")
        elif inst.discharged:
            st.warning("⚠️ Cannot add medicines after discharge.")
        else:
            added = False
            for idx, qty in enumerate((p1, p2, p3, p4, p5), start=1):
                name, price = pharmacy_map[idx]
                # ✅ Always update the quantity (even 0 means reset)
                inst.pharmacy_items[name] = int(qty)
                added = True

            # ✅ Update total charge
            inst.pharmacy_charge = sum(
                inst.pharmacy_items[name] * price for name, price in [v for v in pharmacy_map.values()]
            )

            save_data(st.session_state.patients)
            st.success(f"✅ Pharmacy updated | Total: ₹{inst.pharmacy_charge}")


    # -------- Lab Tests (two columns, persistent) --------
    st.markdown("<hr style='border: 1px solid white'>", unsafe_allow_html=True)
    st.subheader("🧪 Lab Tests :")
    col1, col2 = st.columns(2)

    inst = st.session_state.inst
    patient_suffix = f"_{inst.patient_id}" if inst else ""

    # Initialize lab_items dict if not exists
    if inst and not hasattr(inst, "lab_items"):
        inst.lab_items = {}

    # Map of lab tests
    lab_map = {
        1: ("Blood Test", 400),
        2: ("X-Ray", 800),
        3: ("MRI", 7000),
        4: ("CT Scan", 5000),
        5: ("Ultrasound", 1200),
    }

    # Get existing quantities
    existing_labs = {name: inst.lab_items.get(name, 0) for name, _ in lab_map.values()} if inst else {}

    # Input fields showing saved quantities
    l1 = col1.number_input("Blood Test (₹400)", min_value=0, value=existing_labs.get("Blood Test", 0), key=f"l1_add{patient_suffix}")
    l2 = col1.number_input("X-Ray (₹800)", min_value=0, value=existing_labs.get("X-Ray", 0), key=f"l2_add{patient_suffix}")
    l3 = col1.number_input("MRI (₹7000)", min_value=0, value=existing_labs.get("MRI", 0), key=f"l3_add{patient_suffix}")
    l4 = col2.number_input("CT Scan (₹5000)", min_value=0, value=existing_labs.get("CT Scan", 0), key=f"l4_add{patient_suffix}")
    l5 = col2.number_input("Ultrasound (₹1200)", min_value=0, value=existing_labs.get("Ultrasound", 0), key=f"l5_add{patient_suffix}")

    # Button to update lab tests
    if st.button("➕ Add Lab Tests"):
        if not inst:
            st.warning("⚠️ Create or load a patient first.")
        elif inst.discharged:
            st.warning("⚠️ Cannot add lab tests after discharge.")
        else:
            for idx, qty in enumerate((l1, l2, l3, l4, l5), start=1):
                name, price = lab_map[idx]
                inst.lab_items[name] = int(qty)

            # Update total lab charge
            inst.lab_charge = sum(
                inst.lab_items[name] * price for name, price in [v for v in lab_map.values()]
            )

            save_data(st.session_state.patients)
            st.success(f"✅ Lab Tests updated | Total: ₹{inst.lab_charge}")


    # -------- Billing --------
    st.markdown("<hr style='border: 1px solid white'>", unsafe_allow_html=True)

    st.subheader("🧾 Generate Bill :")

    # Initialize the toggle state
    if "show_bill" not in st.session_state:
        st.session_state.show_bill = False

    # Button to toggle
    if st.button("📄 Show Bill"):
        st.session_state.show_bill = not st.session_state.show_bill  # Toggle True/False

    # Conditionally display the bill
    if st.session_state.show_bill:
        inst = st.session_state.inst
        if not inst:
            st.warning("⚠️ Create or load a patient first.")
        else:
            bill_text = inst.get_bill_text()
            st.text_area("Bill Summary", value=bill_text, height=400)

    # -------- Patient Management --------
    st.markdown("<hr style='border: 2px solid white'>", unsafe_allow_html=True)

    st.subheader("📋 Patient Management :")

    if st.session_state.patients:
        sel = st.selectbox(
            "Select Patient",
            [f"{p.patient_id}: {p.name}{' (DISCHARGED)' if p.discharged else ''}" for p in st.session_state.patients],
        )

        pid = int(sel.split(":")[0])
        selected = next((p for p in st.session_state.patients if p.patient_id == pid), None)

        if selected:
            # st.write(selected.get_bill_text())

            if selected.discharged:
                st.info("✅ Patient already discharged.")
            else:
                col1, col2, col3 = st.columns([1, 0.1, 1])
                with col1:
                    if st.button("Load Patient Form"):
                        st.session_state.inst = selected
                        st.session_state.sidebar_name = selected.name
                        st.session_state.sidebar_age = selected.age
                        st.session_state.sidebar_address = selected.address
                        st.session_state.sidebar_admit = selected.admit_date
                        st.rerun()

                with col3:
                    if st.button("🏁 Discharge Patient"):
                        discharge_date = datetime.today().strftime("%Y-%m-%d") 
                        selected.discharge(discharge_date)
                        save_data(st.session_state.patients)
                        st.success(f"✅ Patient {selected.patient_id} discharged successfully.")

    else:
        st.info("No patients found. Add a new one using the sidebar.")


if __name__ == "__main__":
    main()
