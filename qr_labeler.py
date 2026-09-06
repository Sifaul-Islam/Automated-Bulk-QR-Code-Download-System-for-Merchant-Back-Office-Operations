def label_qr_codes(agents):
    print("Labeling QR codes...")
    for agent in agents:
        print(f"- QR label prepared for {agent.get('id') or agent.get('name')}")
import os
import shutil

def label_qr_files(downloaded_files, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    print("\nLabeling downloaded files...")

    for item in downloaded_files:
        pdf_path    = item["path"]
        batch       = item["batch"]
        first_agent = batch[0]
        agent_type  = first_agent["type"]
        batch_num   = downloaded_files.index(item) + 1

        # Clean filename
        safe_name = first_agent['name']\
            .replace(' ', '_')\
            .replace('/', '-')\
            .replace('\\', '-')\
            .replace(':', '-')\
            .replace('*', '-')\
            .replace('?', '-')\
            .replace('"', '-')\
            .replace('<', '-')\
            .replace('>', '-')\
            .replace('|', '-')

        new_name = f"Batch{batch_num}_{agent_type}_{safe_name}.pdf"
        dst = os.path.join(output_dir, new_name)

        shutil.copy(pdf_path, dst)
        print(f"  Renamed: {new_name}")

        # Create agent list text file sorted by wallet number
        label_file = os.path.join(
            output_dir,
            f"Batch{batch_num}_{agent_type}_agents.txt"
        )

        sorted_batch = sorted(batch, key=lambda x: x["wallet"])

        with open(label_file, "w", encoding="utf-8") as f:
            f.write(f"Batch Number  : {batch_num}\n")
            f.write(f"Type          : {agent_type}\n")
            f.write(f"Total Agents  : {len(batch)}\n")
            f.write("-" * 70 + "\n")
            f.write(f"{'Formatted':<20} {'Wallet No.':<15} {'DBA Name':<30} {'Parent'}\n")
            f.write("-" * 70 + "\n")

            for agent in sorted_batch:
                w = agent['wallet']
                if len(w) == 11:
                    formatted = f"{w[0:3]}-{w[3:7]}-{w[7:11]}"
                elif len(w) == 10:
                    formatted = f"{w[0:3]}-{w[3:7]}-{w[7:10]}"
                else:
                    formatted = w

                f.write(
                    f"{formatted:<20} "
                    f"{agent['wallet']:<15} "
                    f"{agent['name']:<30} "
                    f"{agent['parent']}\n"
                )

        print(f"  Agent list : Batch{batch_num}_{agent_type}_agents.txt")

    print(f"\nAll files saved to: {output_dir}")