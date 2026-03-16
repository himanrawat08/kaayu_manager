INDIAN_CITIES = sorted([
    # Andhra Pradesh
    "Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Kakinada",
    "Rajahmundry", "Tirupati", "Anantapur", "Eluru", "Ongole", "Kadapa", "Chittoor",
    "Vizianagaram", "Srikakulam", "Machilipatnam", "Tenali", "Hindupur", "Bhimavaram",
    # Arunachal Pradesh
    "Itanagar", "Naharlagun", "Pasighat",
    # Assam
    "Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Nagaon", "Tinsukia", "Tezpur",
    "Bongaigaon", "Dhubri", "Diphu",
    # Bihar
    "Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia", "Darbhanga",
    "Bihar Sharif", "Arrah", "Begusarai", "Katihar", "Munger", "Chhapra",
    "Samastipur", "Hajipur", "Sasaram", "Dehri",
    # Chhattisgarh
    "Raipur", "Bhilai", "Bilaspur", "Korba", "Durg", "Rajnandgaon", "Raigarh",
    "Jagdalpur", "Ambikapur", "Chamba",
    # Goa
    "Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda",
    # Gujarat
    "Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar",
    "Junagadh", "Gandhinagar", "Anand", "Morbi", "Nadiad", "Mehsana",
    "Bharuch", "Gandhidham", "Surendranagar", "Porbandar", "Navsari",
    "Valsad", "Godhra", "Patan", "Amreli", "Botad", "Dwarka",
    # Haryana
    "Faridabad", "Gurugram", "Panipat", "Ambala", "Yamunanagar", "Rohtak",
    "Hisar", "Karnal", "Sonipat", "Panchkula", "Bhiwani", "Sirsa",
    "Bahadurgarh", "Jhajjar", "Rewari", "Palwal", "Kaithal", "Kurukshetra",
    # Himachal Pradesh
    "Shimla", "Mandi", "Solan", "Dharamsala", "Baddi", "Palampur",
    "Kullu", "Hamirpur", "Una", "Nahan", "Sundernagar",
    # Jharkhand
    "Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Hazaribagh", "Deoghar",
    "Giridih", "Ramgarh", "Medininagar", "Phusro", "Chaibasa",
    # Karnataka
    "Bengaluru", "Mysuru", "Hubballi", "Dharwad", "Mangaluru", "Belagavi",
    "Kalaburagi", "Davanagere", "Ballari", "Vijayapura", "Shivamogga",
    "Tumkur", "Raichur", "Bidar", "Hassan", "Udupi", "Chikkamagaluru",
    "Mandya", "Chitradurga", "Bagalkot", "Gadag", "Koppal", "Yadgir",
    # Kerala
    "Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kollam",
    "Alappuzha", "Palakkad", "Malappuram", "Kottayam", "Kannur",
    "Kasaragod", "Pathanamthitta", "Idukki", "Wayanad", "Ernakulam",
    "Punalur", "Chalakudy", "Perinthalmanna",
    # Madhya Pradesh
    "Indore", "Bhopal", "Jabalpur", "Gwalior", "Ujjain", "Sagar",
    "Ratlam", "Satna", "Dewas", "Murwara", "Singrauli", "Rewa",
    "Burhanpur", "Khandwa", "Bhind", "Chhindwara", "Guna", "Shivpuri",
    "Vidisha", "Chhatarpur", "Damoh", "Mandsaur", "Khargone", "Neemuch",
    # Maharashtra
    "Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad", "Solapur",
    "Amravati", "Navi Mumbai", "Thane", "Kalyan", "Kolhapur", "Akola",
    "Latur", "Dhule", "Jalgaon", "Ahmednagar", "Chandrapur", "Parbhani",
    "Ichalkaranji", "Sangli", "Malegaon", "Nanded", "Bhiwandi", "Ulhasnagar",
    "Shirdi", "Satara", "Ratnagiri", "Osmanabad", "Wardha", "Buldhana",
    "Yavatmal", "Gondia", "Beed", "Hingoli", "Washim",
    # Manipur
    "Imphal", "Thoubal", "Bishnupur", "Senapati",
    # Meghalaya
    "Shillong", "Tura", "Jowai",
    # Mizoram
    "Aizawl", "Lunglei", "Saiha",
    # Nagaland
    "Kohima", "Dimapur", "Mokokchung",
    # Odisha
    "Bhubaneswar", "Cuttack", "Rourkela", "Brahmapur", "Sambalpur",
    "Puri", "Balasore", "Baripada", "Jharsuguda", "Bargarh",
    "Bhadrak", "Kendujhar", "Angul", "Sundargarh",
    # Punjab
    "Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda",
    "Mohali", "Firozpur", "Pathankot", "Hoshiarpur", "Moga",
    "Batala", "Gurdaspur", "Abohar", "Malerkotla", "Muktsar",
    "Rajpura", "Phagwara", "Khanna", "Barnala", "Sangrur",
    # Rajasthan
    "Jaipur", "Jodhpur", "Kota", "Bikaner", "Ajmer", "Udaipur",
    "Bhilwara", "Alwar", "Sikar", "Sri Ganganagar", "Pali",
    "Tonk", "Barmer", "Churu", "Jhunjhunu", "Nagaur", "Bharatpur",
    "Sawai Madhopur", "Bundi", "Hanumangarh", "Karauli", "Baran",
    "Jalore", "Dungarpur", "Banswara", "Rajsamand", "Pratapgarh",
    "Beawar", "Kishangarh", "Bhiwadi", "Neemrana", "Pushkar",
    # Sikkim
    "Gangtok", "Namchi", "Gyalshing",
    # Tamil Nadu
    "Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem",
    "Tirunelveli", "Tiruppur", "Vellore", "Erode", "Thoothukudi",
    "Dindigul", "Thanjavur", "Ranipet", "Hosur", "Kanchipuram",
    "Kumbakonam", "Cuddalore", "Nagercoil", "Karur", "Udhagamandalam",
    "Sivakasi", "Namakkal", "Pollachi", "Rajapalayam", "Pudukkottai",
    "Krishnagiri", "Villupuram", "Ariyalur", "Nagapattinam", "Mayiladuthurai",
    # Telangana
    "Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Ramagundam",
    "Khammam", "Mahbubnagar", "Secunderabad", "Nalgonda", "Adilabad",
    "Suryapet", "Miryalaguda", "Mancherial", "Siddipet", "Medak",
    "Bhongir", "Jagtial", "Nirmal", "Vikarabad", "Sangareddy",
    # Tripura
    "Agartala", "Dharmanagar", "Udaipur",
    # Uttar Pradesh
    "Lucknow", "Kanpur", "Ghaziabad", "Agra", "Varanasi", "Meerut",
    "Prayagraj", "Bareilly", "Aligarh", "Moradabad", "Saharanpur",
    "Gorakhpur", "Noida", "Firozabad", "Jhansi", "Muzaffarnagar",
    "Mathura", "Hapur", "Rampur", "Shahjahanpur", "Farrukhabad",
    "Mau", "Sultanpur", "Faizabad", "Bahraich", "Sitapur",
    "Bulandshahr", "Sambhal", "Amroha", "Lakhimpur", "Unnao",
    "Etawah", "Gonda", "Deoria", "Ballia", "Jaunpur", "Azamgarh",
    "Hardoi", "Mirzapur", "Bijnor", "Barabanki", "Mainpuri",
    "Greater Noida", "Vrindavan",
    # Uttarakhand
    "Dehradun", "Haridwar", "Roorkee", "Haldwani", "Rudrapur",
    "Kashipur", "Rishikesh", "Kotdwar", "Ramnagar", "Pithoragarh",
    "Nainital", "Mussoorie", "Tehri",
    # West Bengal
    "Kolkata", "Asansol", "Siliguri", "Durgapur", "Bardhaman",
    "Malda", "Baharampur", "Habra", "Kharagpur", "Shantipur",
    "Dankuni", "Howrah", "Haldia", "Raiganj", "Jalpaiguri",
    "Cooch Behar", "Krishnanagar", "Medinipur", "Bankura", "Purulia",
    "Balurghat", "Darjeeling", "Kalimpong", "Berhampore", "Alipurduar",
    # Union Territories
    "New Delhi", "Delhi",
    "Chandigarh",
    "Puducherry", "Karaikal", "Yanam", "Mahe",
    "Srinagar", "Jammu", "Anantnag", "Sopore", "Baramulla",
    "Leh", "Kargil",
    "Port Blair",
    "Silvassa",
    "Daman", "Diu",
    "Kavaratti",
])
